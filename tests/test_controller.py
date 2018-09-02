import asyncio
import pytest

from mock_driver import MockDriver
from zof.configuration import Configuration
from zof.controller import Controller

# pylint: disable=unused-argument


class MockController(Controller):
    """Implements a test controller that uses a mock driver."""

    def __init__(self, **kwds):
        super().__init__(Configuration(driver_class=MockDriver, **kwds))
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


@pytest.mark.asyncio
async def test_basic_controller(caplog):
    """Test controller event dispatch order with sync handlers."""

    controller = MockController()
    exit_status = await controller.run()

    assert exit_status == 0
    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_channel_up(caplog):
    """Test controller event dispatch with an async channel_up handler."""

    class _Controller(MockController):
        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    controller = _Controller()
    exit_status = await controller.run()

    assert exit_status == 0
    assert controller.events == [
        'START', 'CHANNEL_UP', 'NEXT', 'CHANNEL_DOWN', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_channel_up_cancel(caplog):
    """Test controller event dispatch with an async channel_up handler."""

    class _Controller(MockController):
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
    await controller.run()

    assert controller.events == [
        'START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'CANCEL', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_channel_down(caplog):
    """Test controller event dispatch with an async channel_down handler."""

    class _Controller(MockController):
        async def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run()

    assert controller.events == [
        'START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'NEXT', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_start(caplog):
    """Test controller event dispatch with async start."""

    class _Controller(MockController):
        async def on_start(self):
            self.zof_loop.call_later(0.1, self.zof_exit, 0)
            self.events.append('START')
            await asyncio.sleep(0.02)
            self.events.append('NEXT')

    controller = _Controller()
    await controller.run()

    assert controller.events == [
        'START', 'NEXT', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_exceptions(caplog):
    """Test exceptions in async handlers."""

    class _Controller(MockController):
        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            raise Exception('FAIL_ASYNC')

        def on_bogus_event(self, dp, event):
            raise Exception('FAIL_SYNC')

        def on_exception(self, exc):
            self.events.append(str(exc))

    controller = _Controller()
    await controller.run()

    assert controller.events == [
        'START', 'CHANNEL_UP', 'FAIL_SYNC', 'FAIL_ASYNC', 'CHANNEL_DOWN',
        'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_request_benchmark(caplog):
    """Test datapath request() api."""

    class _Controller(MockController):
        async def on_start(self):
            self.zof_driver.channel_wait = 10.0
            self.events.append('START')

        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            try:
                print(await _controller_request_benchmark(
                    'controller_request', dp, 1000))
            finally:
                self.zof_exit(0)

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
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

    bench = {'benchmark': name, 'loops': loops, 'times': []}

    for _ in range(4):
        bench['times'].append(await _test(bench['loops']))

    return bench


@pytest.mark.asyncio
async def test_packet_in_async(caplog):
    """Test packet_in api with async callback."""

    from timeit import default_timer as _timer

    class _Controller(MockController):

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
                bench = {
                    'benchmark': 'packet_in_async',
                    'loops': self.packet_count,
                    'times': [t]
                }
                print(bench)

        def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            self.zof_exit(0)

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_packet_in_sync(caplog):
    """Test packet_in api with sync callback."""

    from timeit import default_timer as _timer

    class _Controller(MockController):

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
                bench = {
                    'benchmark': 'packet_in_sync',
                    'loops': self.packet_count,
                    'times': [t]
                }
                print(bench)

        def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            self.zof_exit(0)

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_controller_invalid_event(caplog):
    """Test controller event dispatch with an invalid event."""

    class _Controller(MockController):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            self.zof_driver.post_event({'notype': 'invalid'})

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [
        ('zof', 50, "Exception in zof_event_loop: KeyError('type')")
    ]


@pytest.mark.asyncio
async def test_controller_unknown_connid(caplog):
    """Test controller event dispatch with an invalid event."""

    class _Controller(MockController):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            self.zof_driver.post_event({'conn_id': 1000, 'type': 'unknown'})

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [('zof', 30, 'Unknown conn_id 1000')]


@pytest.mark.asyncio
async def test_controller_exception_in_handler(caplog):
    """Test controller with async handler that throws exception."""

    class _Controller(MockController):
        async def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            raise RuntimeError('oops')

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [
        ('zof', 50, "Exception in zof handler: RuntimeError('oops')")
    ]


@pytest.mark.asyncio
async def test_controller_channel_alert(caplog):
    """Test controller with channel_alert."""

    class _Controller(MockController):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            self.zof_driver.post_event({
                'conn_id': dp.conn_id,
                'type': 'CHANNEL_ALERT'
            })

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [
        ('zof', 30,
         "CHANNEL_ALERT dp=<Datapath conn_id=2 dpid=00:00:00:00:00:00:00:01> "
         "{'conn_id': 2, 'type': 'CHANNEL_ALERT'}")
    ]


@pytest.mark.asyncio
async def test_controller_all_datapaths(caplog):
    """Test controller's all_datapaths method."""

    class _Controller(MockController):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            assert dp in self.all_datapaths()

        def on_channel_down(self, dp, event):
            self.log_event(dp, event)
            assert dp not in self.all_datapaths()

    controller = _Controller()
    await controller.run()

    assert controller.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_controller_listen_bad_tls_args(caplog):
    """Test controller listen argument with bad TLS args."""

    # N.B. This is _not_ using a mock driver.
    config = Configuration(tls_cert='x')
    controller = Controller(config)
    exit_status = await controller.run()

    assert exit_status != 0
    assert caplog.record_tuples == [
        ('zof', 50,
         "Exception in run: RequestError('ERROR: PEM routines')")
    ]


@pytest.mark.asyncio
async def test_controller_listen_bad_endpoints(caplog):
    """Test controller listen argument with duplicated endpoint."""

    # N.B. This is _not_ using a mock driver.
    config = Configuration(listen_endpoints=['[::1]:26653', '[::1]:26653'])
    controller = Controller(config)
    exit_status = await controller.run()

    assert exit_status != 0
    assert caplog.record_tuples == [(
        'zof', 50,
        "Exception in run: RequestError('ERROR: Address already in use')"
    )]


@pytest.mark.asyncio
async def test_controller_no_listen(caplog):
    """Test controller listen argument zero endpoints."""

    controller = MockController(listen_endpoints=[])
    exit_status = await controller.run()

    assert exit_status == 0
    assert not caplog.record_tuples
