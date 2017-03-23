"""

Events:
    device_up         device=<Device>
    device_down       device=<Device>

    port_added        port=<Port>
    port_deleted
    port_up
    port_down
    port_modified

Event attributes added:
    device
"""

import asyncio
from collections import OrderedDict
from .. import ofp_app, ofp_run, ofp_compile

OPENFLOW_VERSION_1 = 0

OFP = ofp_app('service.device')  #, precedence=-100)

SET_CONFIG = ofp_compile("""
  type: SET_CONFIG
  msg:
    flags: [FRAG_NORMAL]
    miss_send_len: NO_BUFFER
""")
'''
  ---
  type: BARRIER_REQUEST
  ---
  type: GET_CONFIG_REQUEST
'''

GET_CONFIG = ofp_compile("""
  type: GET_CONFIG_REQUEST
""")

DESC_REQ = ofp_compile('type: REQUEST.DESC')
PORT_REQ = ofp_compile('type: REQUEST.PORT_DESC')
PORT_STATS = ofp_compile("""
    type: REQUEST.PORT_STATS
    msg:
      port_no: ANY
""")
BARRIER = ofp_compile('type: BARRIER_REQUEST')

REQ_FLOWS = ofp_compile('''
    type: REQUEST.FLOW
    msg:
      table_id: ALL
      out_port: ANY
      out_group: ANY
      cookie: 0
      cookie_mask: 0
      match: []
''')

DEVICES = OrderedDict()


class Device(object):
    def __init__(self, event):
        self.datapath_id = event.datapath_id
        self.conn_id = event.conn_id
        self.endpoint = event.endpoint
        self.version = event.version
        self.n_buffers = 0
        self.ports = OrderedDict()
        self.dp_desc = ''
        self.mfr_desc = ''
        self.hw_desc = ''
        self.sw_desc = ''
        self.serial_num = ''
        self.name = '<Unknown %d>' % event.conn_id

    def __getstate__(self):
        return self.__dict__

    async def port_mod(self, port_no, *, port_down=False):
        port = self.ports[port_no]
        port_down = 'PORT_DOWN' if port_down else ''
        req = ofp_compile('''
            type: PORT_MOD
            msg:
              port_no: $port_no
              hw_addr: $hw_addr
              config: [ $port_down ]
              mask: [ PORT_DOWN ]
        ''')
        req.send(
            datapath_id=self.datapath_id,
            port_no=port_no,
            hw_addr=port.hw_addr,
            port_down=port_down)


class Port(object):
    def __init__(self, port):
        OFP.logger.info("port %r", port)

        self.port_no = port.port_no
        self.name = port.name
        self.hw_addr = port.hw_addr
        self.config = port.config
        self.state = port.state
        self.ethernet = port.ethernet
        self.stats = None

    def __getstate__(self):
        return self.__dict__

    def update(self, port):
        """Update port data.

        Return 'port_*' event type.
        """
        assert self.port_no == port.port_no

        self.name = port.name
        self.hw_addr = port.hw_addr
        self.ethernet = port.ethernet

        event = ''
        was_down = ('LINK_DOWN' in self.state)
        if was_down != ('LINK_DOWN' in port.state):
            event = 'port_up' if was_down else 'port_down'

        if not event:
            if port.config != self.config or port.state != self.state:
                event = 'port_changed'

        self.state = port.state
        self.config = port.config

        return event

    def up(self):
        return 'LINK_DOWN' not in self.state

    def admin_up(self):
        return 'PORT_DOWN' not in self.config


# TODO(bfish): remove stat polling
#@OFP.event('start')
async def poll_portstats(event):
    while True:
        for device in DEVICES.values():
            if device.ports:
                reply = await PORT_STATS.request(
                    datapath_id=device.datapath_id)
                for stat in reply.msg:
                    device.ports[stat.port_no].stats = stat
                    del stat['port_no']
                    #OFP.logger.info(stat)
        await asyncio.sleep(10.0)


@OFP.message('channel_up')
def channel_up(event):
    DEVICES[event.datapath_id] = Device(event)
    # grab ports here.


@OFP.message('channel_down')
def channel_down(event):
    device = DEVICES[event.datapath_id]
    del DEVICES[event.datapath_id]
    OFP.post_event('device_down', datapath_id=event.datapath_id, device=device)


@OFP.message('features_reply')
async def features_reply(event):
    """Handle FeaturesReply message.
    """
    OFP.logger.debug('features_reply %r', event)
    #print('get_config', await GET_CONFIG.request(datapath_id=event.datapath_id))

    device = DEVICES[event.datapath_id]
    device.n_buffers = event.msg.n_buffers
    device.ports = OrderedDict((i.port_no, Port(i))
                               for i in await _fetch_ports(event))

    if device.n_buffers > 0:
        await _set_config()

    desc = await _fetch_desc()
    device.dp_desc = desc.msg.dp_desc
    device.mfr_desc = desc.msg.mfr_desc
    device.hw_desc = desc.msg.hw_desc
    device.sw_desc = desc.msg.sw_desc
    device.serial_num = desc.msg.serial_num
    #OFP.logger.info('desc %r', desc)

    OFP.post_event('device_up', datapath_id=event.datapath_id, device=device)


@OFP.message('port_status')
def port_status(event):
    """Handle PortStatus message.
    """
    OFP.logger.debug('port_status %r', event)

    device = DEVICES[event.datapath_id]
    msg = event.msg
    port_no = msg.port_no

    if msg.reason == 'ADD':
        port = device.ports[port_no] = Port(msg)
        event = 'port_added'
    elif msg.reason == 'MODIFY':
        port = device.ports[port_no]
        event = port.update(msg)
    elif msg.reason == 'DELETE':
        port = device.ports[port_no]
        del device.ports[port_no]
        event = 'port_deleted'
    else:
        raise ValueError('Unknown port_status reason: %s', msg.reason)

    OFP.post_event(event, port=port)


@OFP.event('port_down')
def port_down(event):
    OFP.logger.warning('port_down: %s', event)


@OFP.event('port_up')
def port_up(event):
    OFP.logger.warning('port_up: %s', event)


async def _fetch_ports(features_reply):

    if features_reply.version == OPENFLOW_VERSION_1:
        return features_reply.msg.ports
    else:
        result = await PORT_REQ.request()
        return result.msg


async def _set_config():
    SET_CONFIG.send()
    #OFP.logger.info('_set_config %r', result)
    return await BARRIER.request()


async def _fetch_desc():
    return await DESC_REQ.request()


@OFP.command('device')
def device_list(event):
    """List all devices.

    ls [-lap] <dpid>
    """
    yield 'VER  NAME               DPID                   ENDPOINT  PORT BUF  CONN'
    for device in DEVICES.values():
        yield '%3d %-20s %s %s  %d %d %d %s' % (
            device.version, device.name, device.datapath_id, device.endpoint,
            len(device.ports), device.n_buffers, device.conn_id,
            device.hw_desc)


@OFP.command('port')
def port_list(event):
    yield 'PORT   NAME        MAC   CONFIG   STATE  TX PKTS BYTES  RX PKTS BYTES'
    for device in DEVICES.values():
        for port in device.ports.values():
            s = port.stats
            if s:
                stats = '%d %d %d %d' % (s.tx_packets, s.tx_bytes,
                                         s.rx_packets, s.rx_bytes)
            else:
                stats = '<nostats>'
            yield '%5s %-20s %s %s %s %s %s' % (port.port_no, port.name,
                                                port.hw_addr, device.name,
                                                port.config, port.state, stats)


@OFP.command('portmod')
async def portmod(event):
    dpid = event.args[0]
    portnum = int(event.args[1])
    device = DEVICES[dpid.lower()]
    await device.port_mod(portnum, port_down=True)


@OFP.command('flows')
async def flows(event):
    for dpid in DEVICES:
        result = await REQ_FLOWS.request(datapath_id=dpid)
        for flow in sorted(
                result.msg, key=lambda x: (x.table_id, -x.priority)):
            print('%s: table %d pri %d %r\n    %r' %
                  (dpid, flow.table_id, flow.priority, flow.match,
                   flow.instructions))


if __name__ == '__main__':
    ofp_run()
