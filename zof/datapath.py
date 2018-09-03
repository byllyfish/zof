"""Implements a Datapath class."""

from zof.log import logger
from zof.packet import Packet
from zof.tasklist import TaskList


class Datapath:
    """Stores info about each connected datapath.

    Attributes:
        id (str): Datapath ID
        conn_id (int): Connection Identifier

    """

    def __init__(self, controller, conn_id, dp_id):
        """Initialize datapath object."""
        self.id = dp_id
        self.conn_id = conn_id
        self.zof_driver = controller.zof_driver
        self.zof_tasks = TaskList(controller.zof_loop, controller.on_exception)

    def send(self, msg):
        """Send message to datapath."""
        logger.debug('Send %r dp=%r', msg['type'], self)

        if msg['type'] == 'PACKET_OUT':
            Packet.zof_to_packet_out(msg)

        msg['conn_id'] = self.conn_id
        self.zof_driver.send(msg)

    async def request(self, msg):
        """Send message to datapath and wait for reply."""
        logger.debug('Send %r dp=%r', msg['type'], self)

        msg['conn_id'] = self.conn_id
        return await self.zof_driver.request(msg)

    def create_task(self, coro):
        """Create managed async task associated with this datapath."""
        self.zof_tasks.create_task(coro)

    def zof_cancel_tasks(self):
        """Cancel tasks when datapath disconnects."""
        self.zof_tasks.cancel()

    def __repr__(self):
        """Return string representation of datapath."""
        return '<Datapath conn_id=%d dpid=%s>' % (self.conn_id, self.id)
