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
        self.zof_loop.call_later(0.01, self.zof_exit, 0)
        self.events.append('START')

    def STOP(self):
        self.events.append('STOP')

    def log_event(self, dp, event):
        self.events.append(event.get('type', event))

    DRIVER_UP = log_event
    DRIVER_DOWN = log_event
    CHANNEL_UP = log_event
    CHANNEL_DOWN = log_event


async def test_basic_controller(caplog):
    """Test controller event dispatch order with sync handlers."""

    controller = BasicController()
    await controller.run()

    assert controller.events == ['DRIVER_UP', 'START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP', 'DRIVER_DOWN']
    assert not caplog.record_tuples


async def test_async_controller(caplog):
    """Test controller event dispatch with a mix of sync/async handlers."""

    class _Controller(BasicController):

        async def CHANNEL_UP(self, dp, event):
            try:
                self.log_event(dp, event)
                await asyncio.sleep(0)
                # The next event is not logged because the task is cancelled.
                self.events.append('NEXT')
            except asyncio.CancelledError:
                # The cancel event is sequenced after the CHANNEL_DOWN.
                self.events.append('CANCEL')

    controller = _Controller()
    await controller.run()

    assert controller.events == ['DRIVER_UP', 'START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'CANCEL', 'STOP', 'DRIVER_DOWN']
    assert not caplog.record_tuples


async def test_async_start(caplog):
    """Test controller event dispatch with async start."""

    class _Controller(BasicController):

        async def START(self):
            self.zof_loop.call_later(0.01, self.zof_exit, 0)
            self.events.append('START')
            await asyncio.sleep(0.02)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run()

    assert controller.events == ['DRIVER_UP', 'START', 'NEXT', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP', 'DRIVER_DOWN']
    assert not caplog.record_tuples
