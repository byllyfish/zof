"""Implements a Controller base class."""

import asyncio
import contextlib
import functools
import logging
import os
import signal

from zoflite.driver import Driver
from zoflite.datapath import Datapath
from zoflite.taskset import TaskSet


LOGGER = logging.getLogger(__package__)

if os.getenv('ZOFDEBUG'):
    logging.basicConfig()
    LOGGER.setLevel(logging.DEBUG)  # pragma: no cover
    LOGGER.debug('ZOFDEBUG enabled')


class ControllerSettings:
    """Settings for a controller."""

    # Options for listening for OpenFlow connections.
    listen_endpoints = ['6653']
    listen_options = ['FEATURES_REQ']
    listen_versions = []

    # Default exit signals.
    exit_signals = [signal.SIGTERM, signal.SIGINT]

    # List of subcontrollers (not implemented yet).
    subcontrollers = []

    # Default driver class.
    driver_class = Driver


class Controller:
    """Base class for a Controller app.

    To create an app, subclass `Controller`, then call the instance's run() 
    coroutine function in an event loop.

    Example:

        class HubController(Controller):

            def PACKET_IN(self, dp, event):
                # Construct a PACKET_OUT message and send it.
                msg = event['msg']
                action = {'action': 'OUTPUT', 'port_no': 'ALL'}
                ofmsg = {
                    'type': 'PACKET_OUT',
                    'msg': {
                        'in_port': msg['in_port'],
                        'actions': [action],
                        'data': msg['data']
                    }
                }
                dp.send(ofmsg)

        # Invoke your controller's run() coroutine in an event loop.
        asyncio.run(HubController().run())

    """

    zof_settings = None
    zof_driver = None
    zof_loop = None
    zof_datapaths = None
    zof_exit_status = None
    zof_tasks = None
    zof_event_queue = None

    async def run(self, *, settings=None):
        """Run controller in an event loop."""

        self.zof_settings = settings or ControllerSettings()
        self.zof_driver = self.zof_settings.driver_class(self.zof_dispatch)

        self.zof_loop = asyncio.get_event_loop()
        self.zof_exit_status = self.zof_loop.create_future()
        self.zof_datapaths = {}
        self.zof_tasks = TaskSet(self.zof_loop)
        self.zof_event_queue = asyncio.Queue()
        self.zof_tasks.create_task(self.zof_event_loop())

        with self.zof_signals_handled():
            async with self.zof_driver:
                # Start app and OpenFlow listener.
                await self.zof_invoke('START')
                await self.zof_listen()

                # Run until we're told to exit.
                await self.zof_exit_status

                # Clean up datapath tasks.
                for dp in self.zof_datapaths.values():
                    dp.zof_cancel_tasks()

                # Clean up controller tasks and stop.
                self.zof_tasks.cancel()
                await self.zof_tasks.wait_cancelled()
                await self.zof_invoke('STOP')

                qsize = self.zof_event_queue.qsize()
                if qsize > 0:
                    LOGGER.warning('Exiting with %d events in queue', qsize)

    def create_task(self, coro):
        """Create a managed async task."""

        self.zof_tasks.create_task(coro)

    def zof_dispatch(self, _driver, event):
        """Post incoming event to our event queue."""

        self.zof_event_queue.put_nowait(event)

    async def zof_event_loop(self):
        """Dispatch events to handler functions."""

        while True:
            event = await self.zof_event_queue.get()
            # TODO(bfish): change oftr dsl.
            msg_type = event['type'].replace('.', '_')

            # Update bookkeeping for connected datapaths.
            if msg_type == 'CHANNEL_UP':
                dp = self.zof_channel_up(event)
            elif msg_type == 'CHANNEL_DOWN':
                dp = self.zof_channel_down(event)
            else:
                dp = self.zof_find_dp(event)

            handler = self.zof_find_handler(msg_type)
            if handler:
                LOGGER.debug('Dispatch %r dp=%r', msg_type, dp)
                await self.zof_dispatch_handler(handler, dp, event)
            else:
                LOGGER.debug('Dispatch %r dp=%r (no handler)', msg_type, dp)

    def zof_find_handler(self, msg_type):
        """Return handler for msg type (or None)."""

        return getattr(self, msg_type, None)

    async def zof_dispatch_handler(self, handler, dp, event):
        """Dispatch to a specific handler function.

        The handler function is scheduled to run as an async task or
        to run in FIFO order (via call_soon). To make debugging easier,
        we wrap the handler call in a function that will catch exceptions and
        report them.
        """

        async def _afwd(handler, dp, event):
            try:
                await handler(dp, event)
            except asyncio.CancelledError:
                pass
            except Exception as ex:  # pylint: disable=broad-except
                self.zof_exception_handler(ex)

        if asyncio.iscoroutinefunction(handler):
            if dp and event['type'] != 'CHANNEL_DOWN':
                dp.create_task(_afwd(handler, dp, event))
            else:
                self.create_task(_afwd(handler, dp, event))
            # Yield time to the newly created task.
            await asyncio.sleep(0)
        else:
            # Invoke handler directly.
            try:
                handler(dp, event)
            except Exception as ex:  # pylint: disable=broad-except
                self.zof_exception_handler(ex)

    def zof_channel_up(self, event):
        """Add the zof Datapath object that represents the event source."""

        conn_id = event['conn_id']
        assert conn_id not in self.zof_datapaths

        # TODO(bfish): change oftr dsl to include features, port_desc in channel_up.
        dp = Datapath(self, conn_id, event)
        self.zof_datapaths[conn_id] = dp
        return dp

    def zof_channel_down(self, event):
        """Remove the zof Datapath object that represents the event source."""

        conn_id = event['conn_id']
        dp = self.zof_datapaths.pop(conn_id)
        dp.zof_cancel_tasks()

    def zof_find_dp(self, event):
        """Find the zof Datapath object for the event source."""

        dp = None
        conn_id = event.get('conn_id')
        if conn_id is not None:
            dp = self.zof_datapaths.get(conn_id)
            if dp is None:
                LOGGER.warning('Unknown conn_id %r', conn_id)

        return dp

    async def zof_listen(self):
        """Tell driver to listen on specific endpoints."""

        if self.zof_settings.listen_endpoints:
            LOGGER.debug('Listen on %r, versions %r', self.zof_settings.listen_endpoints, self.zof_settings.listen_versions)
            coros = [
                self.zof_driver.listen(
                    endpoint,
                    options=self.zof_settings.listen_options,
                    versions=self.zof_settings.listen_versions)
                for endpoint in self.zof_settings.listen_endpoints
            ]
            await asyncio.gather(*coros)

    @contextlib.contextmanager
    def zof_signals_handled(self):
        """Context manager for exit signal handling."""

        def _quit():
            self.zof_exit(0)

        signals = list(self.zof_settings.exit_signals)
        for signum in signals:
            self.zof_loop.add_signal_handler(signum, _quit)

        yield

        for signum in signals:
            self.zof_loop.remove_signal_handler(signum)

    async def zof_invoke(self, msg_type):
        """Notify app to start/stop.

        N.B. The handler is invoked directly from the current task.
        """

        LOGGER.debug('Invoke %r', msg_type)
        handler = getattr(self, msg_type, None)
        if not handler:
            return

        if asyncio.iscoroutinefunction(handler):
            await handler()
        else:
            handler()

    def zof_exit(self, exit_status):
        """Exit controller event loop."""

        self.zof_exit_status.set_result(exit_status)

    def zof_exception_handler(self, exc):
        """Report exception from a zof handler function."""

        LOGGER.exception('zof_exception_handler: %r', exc)
        raise

    def CHANNEL_ALERT(self, dp, event):
        """Default handler for CHANNEL_ALERT message."""

        LOGGER.error('CHANNEL_ALERT received: %r', event)
