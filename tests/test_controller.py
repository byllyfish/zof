"""Test zof.Controller class."""

import asyncio
import pytest
import os
import signal

from mock_driver import MockDriver
import zof

# pylint: disable=unused-argument,missing-docstring


async def mock_controller(app, **kwds):
    config = zof.Configuration(zof_driver_class=MockDriver, exit_signals=[signal.SIGUSR1], **kwds)
    return await zof.run_controller(app, config=config)


def _call_later(timeout, func):
    asyncio.get_event_loop().call_later(timeout, func)


class BasicApp:
    """Implements a test controller that uses a mock driver."""

    def __init__(self):
        self.events = []

    def on_start(self):
        _call_later(0.02, self.quit)
        self.events.append('START')

    def on_stop(self):
        self.events.append('STOP')

    def log_event(self, dp, event):
        self.events.append(event.get('type', event))

    def quit(self):
        os.kill(os.getpid(), signal.SIGUSR1)

    on_channel_up = log_event
    on_channel_down = log_event


@pytest.mark.asyncio
async def test_basic_controller(caplog):
    """Test controller event dispatch order with sync handlers."""

    app = BasicApp()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_channel_up(caplog):
    """Test controller event dispatch with an async channel_up handler."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            assert not dp.closed
            assert dp in zof.get_datapaths()
            assert zof.find_datapath(dp.id) is dp
            dp.create_task(self._channel_up(dp, event))

        async def _channel_up(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == [
        'START', 'CHANNEL_UP', 'NEXT', 'CHANNEL_DOWN', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_channel_up_cancel(caplog):
    """Test controller event dispatch with an async channel_up handler."""

    class _App(BasicApp):
        def on_start(self):
            zof.get_driver().channel_wait = -1
            _call_later(0.01, self.quit)
            self.events.append('START')

        def on_channel_up(self, dp, event):
            dp.create_task(self._channel_up(dp, event))

        async def _channel_up(self, dp, event):
            try:
                self.log_event(dp, event)
                for i in range(3):
                    await asyncio.sleep(0)
                    self.events.append('NEXT%d' % i)
                    # The task is quickly cancelled.
            except asyncio.CancelledError:
                # The cancel event is sequenced after the CHANNEL_DOWN.
                self.events.append('CANCEL')

        def __getattr__(self, attr):
            assert attr.startswith('on_')

            def _other(dp, event):
                self.log_event(dp, event)
            return _other

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == [
        'START', 'CHANNEL_UP', 'BOGUS_EVENT', 'NEXT0', 'CHANNEL_DOWN', 'CANCEL', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_channel_down(caplog):
    """Test controller event dispatch with an async channel_down handler."""

    class _App(BasicApp):
        def on_channel_down(self, dp, event):
            assert dp.closed
            assert dp not in zof.get_datapaths()
            assert zof.find_datapath(dp.id) is None
            zof.create_task(self._channel_down(dp, event))

        async def _channel_down(self, dp, event):
            self.log_event(dp, event)
            await asyncio.sleep(0)
            self.events.append('NEXT')

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == [
        'START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'NEXT', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_async_start(caplog):
    """Test controller event dispatch with async start."""

    class _App(BasicApp):
        async def on_start(self):
            _call_later(0.1, self.quit)
            self.events.append('START')
            await asyncio.sleep(0.02)
            self.events.append('NEXT')

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == [
        'START', 'NEXT', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_exceptions(caplog):
    """Test exceptions in async handlers."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            dp.create_task(self._channel_up(dp, event))

        async def _channel_up(self, dp, event):
            self.log_event(dp, event)
            raise Exception('FAIL_ASYNC')

        def on_bogus_event(self, dp, event):
            raise Exception('FAIL_SYNC')

        def on_exception(self, exc):
            self.events.append(str(exc))

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == [
        'START', 'CHANNEL_UP', 'FAIL_SYNC', 'FAIL_ASYNC', 'CHANNEL_DOWN',
        'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_request_benchmark(caplog):
    """Test datapath request() api."""

    class _App(BasicApp):
        async def on_start(self):
            zof.get_driver().channel_wait = 10.0
            self.events.append('START')

        def on_channel_up(self, dp, event):
            dp.create_task(self._channel_up(dp, event))

        async def _channel_up(self, dp, event):
            self.log_event(dp, event)
            try:
                print(await _controller_request_benchmark(
                    'controller_request', dp, 1000))
            finally:
                self.quit()

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def _controller_request_benchmark(name, dp, loops):
    """Benchmark making async requests."""

    from timeit import default_timer as _timer

    async def _test(loops):
        driver = dp.zof_driver
        desc = {'id': 1, 'method': 'OFP.DESCRIPTION'}
        start_time = _timer()
        for _ in range(loops):
            await driver.request(desc)
        return _timer() - start_time

    bench = {'benchmark': name, 'loops': loops, 'times': []}

    for _ in range(4):
        bench['times'].append(await _test(bench['loops']))

    return bench


@pytest.mark.asyncio
async def test_packet_in_sync(caplog):
    """Test packet_in api with sync callback."""

    from timeit import default_timer as _timer

    class _App(BasicApp):

        packet_limit = 1000
        packet_count = 0
        start_time = 0

        async def on_start(self):
            driver = zof.get_driver()
            driver.channel_wait = 0.001
            driver.packet_count = self.packet_limit
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
            self.quit()

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_controller_invalid_event(caplog):
    """Test controller event dispatch with an invalid event."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            zof.post_event({'notype': 'invalid'})

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [
        ('zof', 50, "Exception in zof_event_loop: KeyError('type')")
    ]


@pytest.mark.asyncio
async def test_controller_unknown_connid(caplog):
    """Test controller event dispatch with an invalid event."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            zof.post_event({'conn_id': 1000, 'type': 'unknown'})

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [('zof', 30, 'Unknown conn_id 1000')]


@pytest.mark.asyncio
async def test_controller_exception_in_handler(caplog):
    """Test controller with async handler that throws exception."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            dp.create_task(self._channel_up(dp, event))

        async def _channel_up(self, dp, event):
            self.log_event(dp, event)
            raise RuntimeError('oops')

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [
        ('zof', 50, "Exception in zof handler: RuntimeError('oops')")
    ]


@pytest.mark.asyncio
async def test_controller_channel_alert(caplog):
    """Test controller with channel_alert."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            zof.post_event({
                'conn_id': dp.conn_id,
                'type': 'CHANNEL_ALERT'
            })

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert caplog.record_tuples == [
        ('zof', 30, "CHANNEL_ALERT <Datapath 0x1 CLOSED> "
         "{'conn_id': 2, 'type': 'CHANNEL_ALERT'}")
    ]


@pytest.mark.asyncio
async def test_controller_all_datapaths(caplog):
    """Test controller's get_datapaths method."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            assert not dp.closed
            self.log_event(dp, event)
            assert dp in zof.get_datapaths()

        def on_channel_down(self, dp, event):
            assert dp.closed
            self.log_event(dp, event)
            assert dp not in zof.get_datapaths()

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_controller_listen_bad_tls_args(caplog):
    """Test controller listen argument with bad TLS args."""

    # N.B. This is _not_ using a mock driver.
    config = zof.Configuration(tls_cert='x')
    app = BasicApp()
    exit_status = await zof.run_controller(app, config=config)

    assert exit_status != 0
    assert caplog.record_tuples == [
        ('zof', 50, "Exception in run: RequestError('ERROR: PEM routines')")
    ]


@pytest.mark.asyncio
async def test_controller_listen_bad_endpoints(caplog):
    """Test controller listen argument with invalid endpoint."""

    # N.B. This is _not_ using a mock driver.
    config = zof.Configuration(listen_endpoints=['[::1]:FOO'])
    app = BasicApp()
    exit_status = await zof.run_controller(app, config=config)

    assert exit_status != 0
    assert len(caplog.record_tuples) == 1

    log_tuple = caplog.record_tuples[0]
    assert log_tuple[:2] == ('zof', 50)
    assert log_tuple[2].startswith(
        "Exception in run: RequestError('ERROR: YAML")


@pytest.mark.asyncio
async def test_controller_no_listen(caplog):
    """Test controller listen argument zero endpoints."""

    app = BasicApp()
    exit_status = await mock_controller(app, listen_endpoints=[])

    assert exit_status == 0
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_controller_custom_event(caplog):
    """Test controller with a custom event."""

    class _App(BasicApp):
        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            zof.post_event({'type': 'FOO'})

        def on_foo(self, dp, event):
            assert dp is None
            self.log_event(dp, event)

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == [
        'START', 'CHANNEL_UP', 'FOO', 'CHANNEL_DOWN', 'STOP'
    ]
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_controller_custom_event_loop(caplog):
    """Test controller with a custom event in a loop.

    This also tests the Controller's anti-starvation
    mechanism in a dispatch loop.
    """

    class _App(BasicApp):
        done = False

        def on_start(self):
            _call_later(0.01, self.stop)
            self.events.append('START')

        def on_channel_up(self, dp, event):
            self.log_event(dp, event)
            zof.post_event({'type': 'FOO'})

        def on_foo(self, dp, event):
            assert dp is None
            # Post another foo event (creating a dispatch loop).
            if not self.done:
                zof.post_event({'type': 'FOO'})

        def stop(self):
            self.done = True
            _call_later(0.01, self.quit)

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status == 0
    assert app.events == ['START', 'CHANNEL_UP', 'CHANNEL_DOWN', 'STOP']
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_exception_in_start_stop(caplog):
    """Test controller with start handler that throws exception."""

    class _App(BasicApp):
        async def on_start(self):
            raise RuntimeError('start failed')

    app = _App()
    exit_status = await mock_controller(app)

    assert exit_status != 0
    assert app.events == []
    assert caplog.record_tuples == [
        ('zof', 50, "Exception in run: RuntimeError('start failed')")
    ]
