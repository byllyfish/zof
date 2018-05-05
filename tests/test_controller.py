import asyncio
import pytest
from zoflite.controller import Controller

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


class MockDriver:
    """Implements a mock OpenFlow driver."""

    dispatch = None

    async def __aenter__(self):
        self.post_event({'type': 'DRIVER_UP'})
        return self

    async def __aexit__(self, *args):
        self.post_event({'type': 'DRIVER_DOWN'})

    async def listen(self, endpoint: str, options=(), versions=()):
        asyncio.ensure_future(self._simulate_channel(2))
        return 1

    def post_event(self, event):
        self.dispatch(self, event)

    async def _simulate_channel(self, conn_id):
        self.post_event({'type': 'CHANNEL_UP', 'conn_id': conn_id, 'datapath_id': '00:00:00:00:00:00:00:01'})
        self.post_event({'type': 'CHANNEL_DOWN', 'conn_id': conn_id})


class BasicController(Controller):
    """Implements a test controller that uses a mock driver."""

    def __init__(self):
        self.zof_driver = MockDriver()
        self.events = []

    def START(self):
        self.events.append('START')
        self.zof_loop.call_later(0.05, self.zof_exit, 0)

    def STOP(self):
        self.events.append('STOP')

    def log_event(self, dp, event):
        self.events.append(event.get('type', event))

    DRIVER_UP = log_event
    DRIVER_DOWN = log_event
    CHANNEL_UP = log_event
    CHANNEL_DOWN = log_event


async def test_basic_controller(caplog):
    """Controller should account for up/down datapaths."""

    controller = BasicController()
    await controller.run()

    assert controller.events == ['DRIVER_UP', 'START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP', 'DRIVER_DOWN']
    assert not caplog.record_tuples
