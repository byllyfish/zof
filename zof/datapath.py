"""Implements a Datapath class."""

from collections import OrderedDict

from zof.log import logger
from zof.packet import Packet
from zof.tasklist import TaskList
from zof.exception import RequestError


class Datapath:
    """Reference to a connected datapath.

    Datapath instances are ephemeral. The instance is destroyed when
    the datapath disconnects and a new instance is created when the
    same datapath ID reconnects. Typically, you will never create a
    Datapath instance; an existing one will be passed to you.

    Attributes:
        id (int): Datapath ID
        conn_id (int): Connection Identifier
        closed (bool): True if datapath is closed
        ports (OrderedDict): Dictionary of port_no -> port_info_dict

    """

    def __init__(self, controller, conn_id, dp_id):
        """Initialize datapath object."""
        self.id = dp_id
        self.conn_id = conn_id
        self.closed = False
        self.ports = OrderedDict()
        self.zof_driver = controller.zof_driver
        self.zof_tasks = TaskList(controller.zof_loop, controller.on_exception)

    def send(self, msg):
        """Send message to datapath."""
        if self.closed:
            raise RequestError.zof_closed()

        if msg['type'] == 'PACKET_OUT':
            Packet.zof_to_packet_out(msg)

        msg['conn_id'] = self.conn_id
        self.zof_driver.send(msg)
        logger.debug('Send %r %s xid=%s', self, msg['type'], msg.get('xid'))

    async def request(self, msg):
        """Send message to datapath and wait for reply."""
        if self.closed:
            raise RequestError.zof_closed()

        logger.debug('Send %r %s (request)', self, msg['type'])
        msg['conn_id'] = self.conn_id
        return await self.zof_driver.request(msg)

    def create_task(self, coro):
        """Create managed async task associated with this datapath."""
        assert not self.closed
        self.zof_tasks.create_task(coro)

    def close(self):
        """Close the datapath preemptively.

        The datapath is not closed until the CHANNEL_DOWN
        event is received from the connection manager. Your datapath
        will still receive incoming events already in flight.
        """
        if not self.closed:
            logger.debug('Close %r', self)
            self.zof_driver.close_nowait(self.conn_id)

    def zof_cancel_tasks(self):
        """Cancel tasks when datapath disconnects."""
        self.zof_tasks.cancel()

    def zof_from_channel_up(self, event):
        """Initialize port information from a CHANNEL_UP event."""
        assert event['type'] == 'CHANNEL_UP'
        new_ports = event['msg']['features']['ports']
        for new_port in new_ports:
            port_no = new_port['port_no']
            self.ports[port_no] = new_port

    def zof_from_port_status(self, event):
        """Update current port information given a PORT_STATUS event."""
        assert event['type'] == 'PORT_STATUS'
        port_status = event['msg']
        port_no = port_status['port_no']
        reason = port_status['reason']
        if reason == 'DELETE':
            self.ports.pop(port_no, None)
        else:
            # Updated port information includes "reason".
            self.ports[port_no] = port_status

    def __repr__(self):
        """Return string representation of datapath."""
        closed_str = ' CLOSED' if self.closed else ''
        return '<Datapath 0x%x%s>' % (self.id, closed_str)
