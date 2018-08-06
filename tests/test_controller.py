import asyncio
import pytest
from zoflite.controller import Controller, ControllerSettings
from mock_driver import MockDriver

# pylint: disable=unused-argument

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


class MockSettings(ControllerSettings):
    driver_class = MockDriver  # type: ignore


class BasicController(Controller):
    """Implements a test controller that uses a mock driver."""

    def __init__(self):
        self.events = []

    def on_start(self):
        self.zof_loop.call_later(0.01, self.zof_exit, 0)
        self.events.append('START')

    def on_stop(self):
        self.events.append('STOP')

    def log_event(self, dp, event):
        self.events.append(event.get('type', event))

    on_channel_up = log_event
    on_channel_down = log_event


async def test_basic_controller(caplog):
    """Test controller event dispatch order with sync handlers."""

    controller = BasicController()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_async_channel_up(caplog):
    """Test controller event dispatch with an async channel_up handler."""

    class _Controller(BasicController):

        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'NEXT', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_async_channel_up_cancel(caplog):
    """Test controller event dispatch with an async channel_up handler."""

    class _Controller(BasicController):

        def on_start(self):
            self.zof_driver.channel_wait = -1
            self.zof_loop.call_later(0.01, self.zof_exit, 0)
            self.events.append('START')

        async def on_channel_up(self, dp, event):
            try:
                self.log_event(dp, event)
                await asyncio.sleep(0)
                # The next event is not logged because the task is cancelled.
                self.events.append('NEXT')
            except asyncio.CancelledError:
                # The cancel event is sequenced after the CHANNEL_DOWN.
                self.events.append('CANCEL')

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'CANCEL', 'STOP']
    assert not caplog.record_tuples


async def test_async_channel_down(caplog):
    """Test controller event dispatch with an async channel_down handler."""

    class _Controller(BasicController):

        async def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'NEXT', 'STOP']
    assert not caplog.record_tuples


async def test_async_start(caplog):
    """Test controller event dispatch with async start."""

    class _Controller(BasicController):

        async def on_start(self):
            self.zof_loop.call_later(0.03, self.zof_exit, 0)
            self.events.append('START')
            await asyncio.sleep(0.02)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'NEXT', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_exceptions(caplog):
    """Test exceptions in async handlers."""

    class _Controller(BasicController):

        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            raise Exception('FAIL')

        def on_exception(self, exc):
            self.events.append(str(exc))

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'FAIL', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_request_benchmark(caplog):
    """Test datapath request() api."""

    class _Controller(BasicController):

        async def on_start(self):
            self.zof_driver.channel_wait = 1.0
            self.events.append('START')

        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            try:
                print(await _controller_request_benchmark('controller_request', dp, 1000))
            finally:
                self.zof_exit(0)

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'STOP']
    assert not caplog.record_tuples


async def _controller_request_benchmark(name, dp, loops):
    """Benchmark making async requests."""

    from timeit import default_timer as _timer

    async def _test(loops):
        driver = dp.zof_driver
        DESC = {'id': 1, 'method': 'OFP.DESCRIPTION'}
        start_time = _timer()
        for _ in range(loops):
            await driver.request(DESC)
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
        packet_count = 0
        start_time = 0

        async def on_start(self):
            self.zof_driver.channel_wait = 0.001
            self.zof_driver.packet_count = self.packet_limit
            self.events.append('START')
            self.start_time = _timer()

        async def on_packet_in(self, dp, event):
            self.packet_count += 1
            if self.packet_count >= self.packet_limit:
                t = _timer() - self.start_time
                bench = { 'benchmark': 'packet_in_async', 'loops': self.packet_count, 'times': [t] }
                print(bench)

        def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            self.zof_exit(0)

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


async def test_packet_in_sync(caplog):
    """Test packet_in api with sync callback.""" 

    from timeit import default_timer as _timer

    class _Controller(BasicController):

        packet_limit = 1000
        packet_count = 0
        start_time = 0

        async def on_start(self):
            self.zof_driver.channel_wait = 0.001
            self.zof_driver.packet_count = self.packet_limit
            self.events.append('START')
            self.start_time = _timer()

        def on_packet_in(self, dp, event):
            self.packet_count += 1
            if self.packet_count >= self.packet_limit:
                t = _timer() - self.start_time
                bench = { 'benchmark': 'packet_in_sync', 'loops': self.packet_count, 'times': [t] }
                print(bench)

        def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            self.zof_exit(0)

    controller = _Controller()
    await controller.run(settings=MockSettings())

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples
