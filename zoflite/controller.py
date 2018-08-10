"""Implements a Controller base class."""

import asyncio
import contextlib
import logging
import os
import signal

from zoflite.driver import Driver
from zoflite.datapath import Datapath
from zoflite.packet import Packet
from zoflite.tasklist import TaskList

LOGGER = logging.getLogger(__package__)

if os.getenv('ZOFDEBUG'):  # pragma: no cover
    logging.basicConfig()
    LOGGER.setLevel(logging.DEBUG)
    LOGGER.debug('ZOFDEBUG enabled')


class ControllerSettings:
    """Settings for a controller."""

    # Options for listening for OpenFlow connections.
    listen_endpoints = ['6653']
    listen_options = ['FEATURES_REQ']
    listen_versions = [4]

    # Default exit signals.
    exit_signals = [signal.SIGTERM, signal.SIGINT]

    # Default driver class.
    driver_class = Driver


class Controller:
    """Base class for a Controller app.

    To create an app, subclass `Controller`, then call the instance's run()
    coroutine function in an event loop.

    Example:

        class HubController(Controller):

            def on_packet_in(self, dp, event):
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

        async def main():
            await HubController().run()

        asyncio.run(main())
    """

    zof_settings = None
    zof_driver = None
    zof_loop = None
    zof_datapaths = None
    zof_exit_status = None
    zof_tasks = None

    async def run(self, *, settings=None):
        """Run controller in an event loop."""
        self.zof_settings = settings or ControllerSettings()
        self.zof_driver = self.zof_settings.driver_class()

        self.zof_loop = asyncio.get_event_loop()
        self.zof_exit_status = self.zof_loop.create_future()
        self.zof_datapaths = {}
        self.zof_tasks = TaskList(self.zof_loop, self.on_exception)
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

                qsize = self.zof_driver.event_queue.qsize()
                if qsize > 0:  # pragma: no cover
                    LOGGER.warning('Exiting with %d events in queue', qsize)

    def create_task(self, coro):
        """Create a managed async task."""
        self.zof_tasks.create_task(coro)

    async def zof_event_loop(self):
        """Dispatch events to handler functions."""
        event_queue = self.zof_driver.event_queue

        while True:
            event = await event_queue.get()
            assert isinstance(event, dict), repr(event)
            event_type = event['type'].replace('.', '_')

            # Update bookkeeping for connected datapaths.
            if event_type == 'CHANNEL_UP':
                dp = self.zof_channel_up(event)
            elif event_type == 'CHANNEL_DOWN':
                dp = self.zof_channel_down(event)
            else:
                dp = self.zof_find_dp(event)
                if event_type == 'PACKET_IN':
                    Packet.zof_from_packet_in(event)

            handler = self.zof_find_handler(event_type)
            if handler:
                LOGGER.debug('Receive %r dp=%r', event_type, dp)
                await self.zof_dispatch_handler(handler, dp, event)
            else:
                LOGGER.debug('Receive %r dp=%r (no handler)', event_type, dp)

    async def zof_dispatch_handler(self, handler, dp, event):
        """Dispatch to a specific handler function."""
        if asyncio.iscoroutinefunction(handler):
            if dp and event['type'] != 'CHANNEL_DOWN':
                create_task = dp.create_task
            else:
                create_task = self.create_task
            create_task(handler(dp, event))
            # Yield time to the newly created task.
            await asyncio.sleep(0)
        else:
            # Invoke handler directly.
            try:
                handler(dp, event)
            except Exception as ex:  # pylint: disable=broad-except
                self.on_exception(ex)

    def zof_channel_up(self, event):
        """Add the zof Datapath object that represents the event source."""
        conn_id = event['conn_id']
        assert conn_id not in self.zof_datapaths

        dp = Datapath(self, conn_id, event)
        self.zof_datapaths[conn_id] = dp
        return dp

    def zof_channel_down(self, event):
        """Remove the zof Datapath object that represents the event source."""
        conn_id = event['conn_id']
        dp = self.zof_datapaths.pop(conn_id)
        dp.zof_cancel_tasks()
        return dp

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
            LOGGER.debug('Listen on %r, versions %r',
                         self.zof_settings.listen_endpoints,
                         self.zof_settings.listen_versions)
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

    async def zof_invoke(self, event_type):
        """Notify app to start/stop."""
        LOGGER.debug('Invoke %r', event_type)
        handler = self.zof_find_handler(event_type)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    def zof_find_handler(self, event_type):
        """Return handler function for given event type."""
        return getattr(self, 'on_%s' % event_type.lower(), None)

    def zof_exit(self, exit_status):
        """Exit controller event loop."""
        self.zof_exit_status.set_result(exit_status)

    def on_exception(self, exc):
        """Report exception from a zof handler function."""
        LOGGER.critical('EXCEPTION: %r', exc)

    def on_channel_alert(self, dp, event):
        """Handle CHANNEL_ALERT message."""
        LOGGER.error('CHANNEL_ALERT dp=%r %r', dp, event)
