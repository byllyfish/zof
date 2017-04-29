"""
Events Produced:
    device_up         device=<Device>
    device_down       device=<Device>

    port_added        port=<Port>
    port_deleted
    port_up
    port_down
    port_modified
"""

import asyncio
from collections import OrderedDict
from .. import ofp_app, ofp_run, ofp_compile

OPENFLOW_VERSION_1 = 0

app = ofp_app('service.device')  #, precedence=-100)
app.devices = OrderedDict()

SET_CONFIG = ofp_compile('''
  type: SET_CONFIG
  msg:
    flags: [FRAG_NORMAL]
    miss_send_len: NO_BUFFER
''')

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
        app.logger.info("port %r", port)

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

    def is_up(self):
        return 'LINK_DOWN' not in self.state

    def is_admin_up(self):
        return 'PORT_DOWN' not in self.config


# TODO(bfish): remove stat polling
#@app.event('start')
async def poll_portstats(_event):
    while True:
        for device in DEVICES.values():
            if device.ports:
                reply = await PORT_STATS.request(
                    datapath_id=device.datapath_id)
                for stat in reply.msg:
                    device.ports[stat.port_no].stats = stat
                    del stat['port_no']
                    #app.logger.info(stat)
        await asyncio.sleep(10.0)


@app.message('channel_up')
def channel_up(event):
    if event.datapath_id in app.devices:
        app.logger.warning('Device %s already exists: %r', event.datapath_id, app.devices[event.datapath_id])
    app.devices[event.datapath_id] = Device(event)


@app.message('channel_down')
def channel_down(event):
    device = app.devices.get(event.datapath_id)
    if device:
        del app.devices[event.datapath_id]
        app.post_event('device_down', datapath_id=event.datapath_id, device=device)
    else:
        app.logger.warning('Device %s does not exist!', event.datapath_id)


@app.message('features_reply')
async def features_reply(event):
    """Handle FeaturesReply message."""
    app.logger.debug('features_reply %r', event)
    #print('get_config', await GET_CONFIG.request(datapath_id=event.datapath_id))

    device = app.devices[event.datapath_id]
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
    #app.logger.info('desc %r', desc)

    app.post_event('device_up', datapath_id=event.datapath_id, device=device)


@app.message('port_status')
def port_status(event):
    """Handle PortStatus message.
    """
    app.logger.debug('port_status %r', event)

    device = app.devices[event.datapath_id]
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

    app.post_event(event, port=port)


@app.event('port_down')
def port_down(event):
    app.logger.warning('port_down: %s', event)


@app.event('port_up')
def port_up(event):
    app.logger.warning('port_up: %s', event)


async def _fetch_ports(features_reply):

    if features_reply.version == OPENFLOW_VERSION_1:
        return features_reply.msg.ports
    else:
        result = await PORT_REQ.request()
        return result.msg


async def _set_config():
    SET_CONFIG.send()
    #app.logger.info('_set_config %r', result)
    return await BARRIER.request()


async def _fetch_desc():
    return await DESC_REQ.request()


@app.command('device')
def device_list(_event):
    """List all devices.

    ls [-lap] <dpid>
    """
    yield 'VER  NAME               DPID                   ENDPOINT  PORT BUF  CONN'
    for device in app.devices.values():
        yield '%3d %-20s %s %s  %d %d %d %s' % (
            device.version, device.name, device.datapath_id, device.endpoint,
            len(device.ports), device.n_buffers, device.conn_id,
            device.hw_desc)


@app.command('port')
def port_list(_event):
    yield 'PORT   NAME        MAC   CONFIG   STATE  TX PKTS BYTES  RX PKTS BYTES'
    for device in app.devices.values():
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


@app.command('portmod')
async def portmod(event):
    dpid = event.args[0]
    portnum = int(event.args[1])
    device = app.devices[dpid.lower()]
    await device.port_mod(portnum, port_down=True)


@app.command('flows')
async def flows(_event):
    for dpid in app.devices:
        result = await REQ_FLOWS.request(datapath_id=dpid)
        for flow in sorted(
                result.msg, key=lambda x: (x.table_id, -x.priority)):
            print('%s: table %d pri %d %r\n    %r' %
                  (dpid, flow.table_id, flow.priority, flow.match,
                   flow.instructions))


if __name__ == '__main__':
    ofp_run()
