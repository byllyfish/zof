"""

Events:
    device_ready

    port_added
    port_deleted
    port_up
    port_down
    port_modified

Event attributes added:
    device
"""

import asyncio
from pylibofp import ofp_app
from collections import OrderedDict


OPENFLOW_VERSION_1 = 0


OFP = ofp_app('service.device')  #, precedence=-100)

SET_CONFIG = OFP.compile("""
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

DESC_REQ = OFP.compile('type: REQUEST.DESC')
PORT_REQ = OFP.compile('type: REQUEST.PORT_DESC')
BARRIER = OFP.compile('type: BARRIER_REQUEST')

DEVICES = OrderedDict()


class Device(object):
    def __init__(self, event):
        self.datapath_id = event.datapath_id
        self.conn_id = event.conn_id
        self.endpoint = event.endpoint
        self.version = event.version
        self.n_buffers = 0
        self.ports = OrderedDict()
        self.desc = None

    def __getstate__(self):
        return self.__dict__


class Port(object):
    def __init__(self, port):
        OFP.logger.debug('Port %r', port)
        self.port_no = port.port_no
        self.name = port.name
        self.hw_addr = port.hw_addr
        self.config = port.config
        self.state = port.state

    def __getstate__(self):
        return self.__dict__

    @property
    def up(self):
        return 'LINK_DOWN' not in self.state

    @property
    def admin_up(self):
        return 'PORT_DOWN' not in self.config



@OFP.message('channel_up')
def channel_up(event):
    DEVICES[event.datapath_id] = Device(event)


@OFP.message('channel_down')
def channel_down(event):
    del DEVICES[event.datapath_id]


@OFP.message('features_reply')
async def features_reply(event):
    """Handle FeaturesReply message.
    """
    OFP.logger.debug('features_reply %r', event)

    device = DEVICES[event.datapath_id]
    device.n_buffers = event.msg.n_buffers
    device.ports = OrderedDict((i.port_no, Port(i)) for i in await _fetch_ports(event))

    if device.n_buffers > 0:
        await _set_config(event.datapath_id)

    OFP.post_event('device_ready', device=device)





@OFP.message('port_status')
def port_status(event):
    """Handle PortStatus message.
    """
    OFP.logger.debug('port_status %r', event)

    device = DEVICES[event.datapath_id]
    port_new = Port(event.msg.port)
    port_no = port_new.port_no
    port_old = device.ports.get(port_no)
    reason = event.msg.reason

    if reason == 'ADD':
        device.ports[port_no] = port_new
        event = 'port_added'
    elif reason == 'MODIFY':
        device.ports[port_no] = port_new
        if port_old.up() != port_new.up():
            event = 'port_up' if port_new.up() else 'port_down'
        elif port_old != port_new:
            event = 'port_modified'
    elif reason == 'DELETE':
        del device.ports[port_no]
        event = 'port_deleted'
    else:
        raise ValueError('Unknown port_status reason: %s', reason)

    OFP.post_event(event, port=port_new, old=port_old)


async def _fetch_ports(features_reply):

    if features_reply.version == OPENFLOW_VERSION_1:
        return features_reply.msg.ports
    else:
        result = await PORT_REQ.request(datapath_id=features_reply.datapath_id)
        return result.msg

async def _set_config(datapath_id):
    SET_CONFIG.send(datapath_id=datapath_id)
    #OFP.logger.info('_set_config %r', result)
    return await BARRIER.request(datapath_id=datapath_id)
