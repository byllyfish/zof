import asyncio
import pytest
from zoflite.controller import Controller

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


class MockDriver:
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
        await asyncio.sleep(0.01)
        self.post_event({'type': 'CHANNEL_UP', 'conn_id': conn_id, 'datapath_id': '00:00:00:00:00:00:00:01'})
        self.post_event({'type': 'CHANNEL_DOWN', 'conn_id': conn_id})


async def test_channel_up(caplog):
    """Controller should account for up/down datapaths."""

    class TestController(Controller):

        def __init__(self, driver):
            self.zof_driver = driver
            self.events = []

        def START(self):
            self.events.append('START')
            self.zof_loop.call_later(0.05, self.zof_exit, 0)

        def STOP(self):
            self.events.append('STOP')

        def _log_event(self, dp, event):
            self.events.append(event)

        DRIVER_UP = _log_event
        DRIVER_DOWN = _log_event
        CHANNEL_UP = _log_event
        CHANNEL_DOWN = _log_event


    controller = TestController(MockDriver())
    await controller.run()

    assert controller.events == [{'type': 'DRIVER_UP'}, 'START', {'type': 'CHANNEL_UP', 'conn_id': 2, 'datapath_id': '00:00:00:00:00:00:00:01'}, {'type': 'CHANNEL_DOWN', 'conn_id': 2}, 'STOP', {'type': 'DRIVER_DOWN'}]
    assert not caplog.record_tuples
