"""Mock Driver class for testing."""

import asyncio

# pylint: disable=unused-argument


class MockDriver:
    """Implements a mock OpenFlow driver."""

    channel_wait = 0.001
    packet_count = 0
    sim_task = None

    def __init__(self):
        """Initialize mock driver."""
        self.event_queue = None

    async def __aenter__(self):
        """Mock async context manager."""
        self.event_queue = asyncio.Queue()
        return self

    async def __aexit__(self, *args):
        """Mock async context manager."""
        if self.sim_task and not self.sim_task.done():
            self.sim_task.cancel()

    async def listen(self, endpoint, options=(), versions=(), tls_id=0):
        """Mock listen method."""
        self.sim_task = asyncio.ensure_future(self._simulate_channel(2))
        return 1

    def send(self, msg):
        """Mock send method."""
        assert isinstance(msg, dict)

    async def request(self, msg):
        """Mock request method."""
        await asyncio.sleep(0)
        xid = msg.get('id')
        if xid is None:
            xid = msg.get('xid')
            return {'xid': xid}
        return {'id': xid}

    def close_nowait(self, conn_id):
        """Mock close_nowait method."""
        assert isinstance(conn_id, int)

    def post_event(self, event):
        """Mock post_event method."""
        self.event_queue.put_nowait(event)

    async def _simulate_channel(self, conn_id):
        self.post_event({
            'type': 'CHANNEL_UP',
            'conn_id': conn_id,
            'datapath_id': '00:00:00:00:00:00:00:01'
        })
        self.post_event({
            'type': 'BOGUS_EVENT',
            'conn_id': conn_id,
            'datapath_id': '00:00:00:00:00:00:00:01'
        })
        for _ in range(self.packet_count):
            packet_in = {
                'type': 'PACKET_IN',
                'conn_id': conn_id,
                'msg': {
                    '_pkt': [],
                    'data': ''
                }
            }
            self.post_event(packet_in)
        if self.channel_wait >= 0:
            await asyncio.sleep(self.channel_wait)
        self.post_event({'type': 'CHANNEL_DOWN', 'conn_id': conn_id})
