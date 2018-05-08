import asyncio
import pytest
from zoflite.controller import Controller

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


class MockDriver:
    """Implements a mock OpenFlow driver."""

    dispatch = None
    channel_wait = -1
    packet_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.sim_task

    async def listen(self, endpoint: str, options=(), versions=()):
        self.sim_task = asyncio.ensure_future(self._simulate_channel(2))
        return 1

    async def request(self, msg):
        await asyncio.sleep(0)
        return {'id': msg['id']}

    def post_event(self, event):
        self.dispatch(self, event)

    async def _simulate_channel(self, conn_id):
        self.post_event({'type': 'CHANNEL_UP', 'conn_id': conn_id, 'datapath_id': '00:00:00:00:00:00:00:01'})
        packet_in = {'type': 'PACKET_IN', 'conn_id': conn_id}
        for _ in range(self.packet_count):
            self.post_event(packet_in)
        if self.channel_wait >= 0:
            await asyncio.sleep(self.channel_wait)
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

    CHANNEL_UP = log_event
    CHANNEL_DOWN = log_event


async def test_basic_controller(caplog):
    """Test controller event dispatch order with sync handlers."""

    controller = BasicController()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_async_channel_up(caplog):
    """Test controller event dispatch with an async channel_up handler."""

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

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'CANCEL', 'STOP']
    assert not caplog.record_tuples


async def test_async_channel_down(caplog):
    """Test controller event dispatch with an async channel_down handler."""

    class _Controller(BasicController):

        async def CHANNEL_DOWN(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'NEXT', 'STOP']
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

    assert controller.events == ['START', 'NEXT', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_exceptions(caplog):
    """Test exceptions in async handlers."""

    class _Controller(BasicController):

        async def CHANNEL_UP(self, dp, event):
            self.log_event(dp, event)
            raise Exception('FAIL')

        def zof_exception_handler(self, exc):
            self.events.append(str(exc))

    controller = _Controller()
    await controller.run()

    print(controller.events)
    assert controller.events == ['START', 'CHANNEL_UP', 'FAIL', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_request_benchmark(caplog):
    """Test datapath request() api."""

    class _Controller(BasicController):

        async def START(self):
            self.zof_driver.channel_wait = 0.25
            self.events.append('START')

        async def CHANNEL_UP(self, dp, event):
            try:
                print(await _controller_request_benchmark('controller_request', dp, 1000))
            finally:
                self.zof_exit(0)

    controller = _Controller()
    await controller.run()

    assert not caplog.record_tuples


async def _controller_request_benchmark(name, dp, loops):
    """Benchmark making async requests."""

    from timeit import default_timer as _timer

    async def _test(loops):
        DESC = {'id': 1, 'method': 'OFP.DESCRIPTION'}
        start_time = _timer()
        for _ in range(loops):
            await dp.request(DESC)
        return _timer() - start_time

    bench = { 'benchmark': name, 'loops': loops, 'times': [] }

    for _ in range(4):
        bench['times'].append(await _test(bench['loops']))

    return bench


async def test_packet_in_async(caplog):
    """Test packet_in api with async callback.""" 

    from timeit import default_timer as _timer

    class _Controller(BasicController):

        packet_limit = 1000

        async def START(self):
            self.zof_driver.channel_wait = 0.001
            self.zof_driver.packet_count = self.packet_limit
            self.events.append('START')
            self.packet_count = 0
            self.start_time = _timer()

        async def PACKET_IN(self, dp, event):
            await asyncio.sleep(0)
            self.packet_count += 1
            if self.packet_count >= self.packet_limit:
                t = _timer() - self.start_time
                bench = { 'benchmark': 'packet_in_async', 'loops': self.packet_count, 'times': [t] }
                print(bench)

        def CHANNEL_DOWN(self, dp, event):
            self.zof_exit(0)

    controller = _Controller()
    await controller.run()

    assert not caplog.record_tuples


async def test_packet_in_sync(caplog):
    """Test packet_in api with sync callback.""" 

    from timeit import default_timer as _timer

    class _Controller(BasicController):

        packet_limit = 1000

        async def START(self):
            self.zof_driver.channel_wait = 0.001
            self.zof_driver.packet_count = self.packet_limit
            self.events.append('START')
            self.packet_count = 0
            self.start_time = _timer()

        def PACKET_IN(self, dp, event):
            self.packet_count += 1
            if self.packet_count >= self.packet_limit:
                t = _timer() - self.start_time
                bench = { 'benchmark': 'packet_in_sync', 'loops': self.packet_count, 'times': [t] }
                print(bench)

        def CHANNEL_DOWN(self, dp, event):
            self.zof_exit(0)

    controller = _Controller()
    await controller.run()

    assert not caplog.record_tuples
