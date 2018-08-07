import asyncio

# pylint: disable=unused-argument


class MockDriver:
    """Implements a mock OpenFlow driver."""

    channel_wait = 0.001
    packet_count = 0
    sim_task = None

    def __init__(self, dispatch=None):
        self.dispatch = dispatch

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.sim_task

    async def listen(self, endpoint, options=(), versions=()):
        self.sim_task = asyncio.ensure_future(self._simulate_channel(2))
        return 1

    def send(self, msg):
        assert isinstance(msg, dict)

    async def request(self, msg):
        await asyncio.sleep(0)
        xid = msg.get('id')
        if xid is None:
            xid = msg.get('xid')
            return {'xid': xid}
        else:
            return {'id': xid}

    def post_event(self, event):
        self.dispatch(self, event)

    async def _simulate_channel(self, conn_id):
        self.post_event({
            'type': 'CHANNEL_UP',
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
