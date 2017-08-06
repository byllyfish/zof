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

from collections import OrderedDict
import zof
from ..event import make_event

app = zof.Application('service.device', precedence=1000000)
app.devices = OrderedDict()

desc = zof.compile('type: REQUEST.DESC')

portdesc = zof.compile('type: REQUEST.PORT_DESC')

barrier = zof.compile('type: BARRIER_REQUEST')


class Device(object):
    """Concrete class to represent a switch.
    """

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
        self.name = '<%s>' % event.datapath_id
        self.device_up = False

    def __getstate__(self):
        return self.__dict__


class Port(object):
    """Concrete class to represent a switch port.
    """

    def __init__(self, port_msg):
        app.logger.debug('port %s', port_msg.port_no)
        self.port_no = port_msg.port_no
        self.name = port_msg.name
        self.hw_addr = port_msg.hw_addr
        self.config = port_msg.config
        self.state = port_msg.state
        self.ethernet = port_msg.ethernet

    def __getstate__(self):
        return self.__dict__

    def update(self, port_msg):
        """Update port data.

        Return event object
        """
        assert self.port_no == port_msg.port_no

        self.name = port_msg.name
        self.hw_addr = port_msg.hw_addr
        self.ethernet = port_msg.ethernet

        event = ''
        was_down = ('LINK_DOWN' in self.state)
        if was_down != ('LINK_DOWN' in port_msg.state):
            event = 'port_up' if was_down else 'port_down'

        if not event:
            if port_msg.config != self.config or port_msg.state != self.state:
                event = 'port_modified'

        self.state = port_msg.state
        self.config = port_msg.config

        return make_event(event=event, port=self)

    def is_up(self):
        return 'LINK_DOWN' not in self.state

    def is_admin_up(self):
        return 'PORT_DOWN' not in self.config


@app.message('channel_up')
def channel_up(event):
    app.logger.debug('channel_up: conn_id=%d', event.conn_id)
    if event.datapath_id in app.devices:
        app.logger.warning('Device %s already exists: %r', event.datapath_id,
                           app.devices[event.datapath_id])
    app.devices[event.datapath_id] = Device(event)


@app.message('channel_down')
def channel_down(event):
    app.logger.debug('channel_down: conn_id=%d', event.conn_id)
    device = app.devices.get(event.datapath_id)
    if not device:
        app.logger.warning('Device %s does not exist! conn_id=%d',
                           event.datapath_id, event.conn_id)
        return

    del app.devices[event.datapath_id]

    if device.device_up:
        app.logger.info('DEVICE_DOWN %s (%s) [version=%d]', device.datapath_id,
                        device.endpoint, device.version)
        app.post_event(
            'device_down', datapath_id=event.datapath_id, device=device)
    else:
        app.logger.warning('DEVICE_HICCUP %s (%s) [version=%d]',
                           device.datapath_id, device.endpoint, device.version)


@app.message('features_reply')
async def features_reply(event):
    """Handle FeaturesReply message."""
    device = app.devices.get(event.datapath_id)
    if not device:
        app.logger.warning('Device %s does not exist! conn_id=%d',
                           event.datapath_id, event.conn_id)
        return

    app.logger.debug('features_reply %r', event)
    # print('get_config', await GET_CONFIG.request(datapath_id=event.datapath_id))

    device = app.devices[event.datapath_id]
    device.n_buffers = event.msg.n_buffers
    device.ports = OrderedDict((i.port_no, Port(i))
                               for i in await _fetch_ports(event))

    d = await desc.request()
    device.dp_desc = d.msg.dp_desc
    device.mfr_desc = d.msg.mfr_desc
    device.hw_desc = d.msg.hw_desc
    device.sw_desc = d.msg.sw_desc
    device.serial_num = d.msg.serial_num
    # app.logger.info('desc %r', desc)

    device.device_up = True
    app.logger.info('DEVICE_UP %s (%s) "%s %s" [version=%d]',
                    device.datapath_id, device.endpoint, device.hw_desc,
                    device.sw_desc, device.version)
    app.post_event('device_up', datapath_id=event.datapath_id, device=device)


@app.message('port_status')
def port_status(event):
    """Handle PortStatus message.
    """
    app.logger.debug('port_status %r', event)

    device = app.devices[event.datapath_id]
    msg = event.msg
    port_no = msg.port_no
    exists = port_no in device.ports

    if msg.reason == 'ADD':
        if exists:
            app.logger.warning('PORT_STATUS:ADD for existing port %r', port_no)
        device.ports[port_no] = Port(msg)
    elif not exists:
        app.logger.warning('PORT_STATUS:%s for unknown port %r', msg.reason,
                           port_no)
        return

    port = device.ports[port_no]
    change_event = port.update(msg)

    if change_event.event == 'PORT_DELETED':
        del device.ports[port_no]

    app.post_event(change_event)


@app.event('port_down')
def port_down(event):
    app.logger.warning('port_down: %s', event)


@app.event('port_up')
def port_up(event):
    app.logger.warning('port_up: %s', event)


async def _fetch_ports(reply):
    if reply.version == 1:
        return reply.msg.ports
    result = await portdesc.request()
    return result.msg


async def _fetch_desc():
    return await desc.request()


def get_devices():
    return app.devices.values()


def get_device_port(datapath_id, port_no):
    device = app.devices[datapath_id]
    return device.ports[port_no]


if __name__ == '__main__':
    zof.run()
