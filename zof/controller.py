"""Implements a Controller base class."""

import asyncio
import contextlib

from zof.configuration import Configuration
from zof.datapath import Datapath
from zof.log import logger
from zof.packet import Packet
from zof.tasklist import TaskList


RUN_STATUS_OKAY = 0
RUN_STATUS_ERROR = 10


class Controller:
    """Base class for a Controller app.

    To create an app, subclass `Controller`, then call the instance's run()
    coroutine function in an event loop.

    Example::

        import asyncio
        import zof

        class HubController(zof.Controller):
            def on_packet_in(self, dp, event):
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

        asyncio.run(HubController().run())

    To handle OpenFlow events, implement methods of the form::

        on_channel_up(dp, event)
        on_channel_down(dp, event)
        on_channel_alert(dp, event)
        on_packet_in(dp, event)
        on_port_status(dp, event)
        on_flow_removed(dp, event)
        on_<MSGTYPE>(dp, event)

    To handle lifecycle events, implement methods of the form::

        on_start()
        on_stop()
        on_exception(exc)

    """

    zof_loop = None
    zof_datapaths = None
    zof_exit_status = None
    zof_tasks = None

    def __init__(self, config=None):
        """Initialize controller with configuration object."""
        self.zof_config = config or Configuration()
        self.zof_driver = self.zof_config.driver_class()

    async def run(self):
        """Run controller in an event loop."""
        self.zof_loop = asyncio.get_event_loop()
        self.zof_exit_status = self.zof_loop.create_future()
        self.zof_datapaths = {}
        self.zof_tasks = TaskList(self.zof_loop, self.on_exception)
        self.zof_tasks.create_task(self.zof_event_loop())

        exit_status = RUN_STATUS_OKAY
        with self.zof_signals_handled():
            async with self.zof_driver:
                try:
                    # Start app and OpenFlow listener.
                    await self.zof_invoke('START')
                    await self.zof_listen()

                    # Run until we're told to exit.
                    await self.zof_exit_status

                    await self.zof_cleanup()
                    await self.zof_invoke('STOP')

                except Exception as ex:  # pylint: disable=broad-except
                    logger.critical(
                        'Exception in run: %r', ex, exc_info=True)
                    exit_status = RUN_STATUS_ERROR
                    await self.zof_cleanup()

        return exit_status

    def create_task(self, coro):
        """Create an async task to run the coroutine.

        The task will be automatically cancelled before the Controller
        is stopped (if still running). If the task fails with an exception,
        the Controller's on_exception(exc) handler will be called.

        Args:
            coro (coroutine object): coroutine to run in task

        Returns:
            asyncio.Task

        """
        return self.zof_tasks.create_task(coro)

    def all_datapaths(self):
        """Return a list of connected datapaths.

        Returns:
            List[zof.Datapath]

        """
        return list(self.zof_datapaths.values())

    async def zof_event_loop(self):
        """Dispatch events to handler functions."""
        event_queue = self.zof_driver.event_queue

        while True:
            try:
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
                    logger.debug('Receive %r dp=%r', event_type, dp)
                    await self.zof_dispatch_handler(handler, dp, event)
                else:
                    logger.debug('Receive %r dp=%r (no handler)', event_type,
                                 dp)

            except asyncio.CancelledError:
                return

            except Exception as ex:  # pylint: disable=broad-except
                logger.critical(
                    'Exception in zof_event_loop: %r', ex, exc_info=True)

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

        dp = Datapath(self, conn_id, event['datapath_id'])
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
                logger.warning('Unknown conn_id %r', conn_id)
        return dp

    async def zof_listen(self):
        """Tell driver to listen on configured endpoints."""
        config = self.zof_config
        if not config.listen_endpoints:
            return

        logger.debug('Listen on %r, versions %r', config.listen_endpoints,
                     config.listen_versions)

        tls_id = 0
        if config.tls_cert:
            # Set up TLS.
            tls_id = await self.zof_driver.add_identity(
                cert=config.tls_cert,
                cacert=config.tls_cacert,
                privkey=config.tls_privkey)

        coros = [
            self.zof_driver.listen(
                endpoint,
                options=['FEATURES_REQ'],
                versions=config.listen_versions,
                tls_id=tls_id) for endpoint in config.listen_endpoints
        ]
        await asyncio.gather(*coros)

    async def zof_cleanup(self):
        """Clean up datapath and controller tasks."""
        for dp in self.zof_datapaths.values():
            dp.zof_cancel_tasks()

        self.zof_tasks.cancel()
        await self.zof_tasks.wait_cancelled()

    @contextlib.contextmanager
    def zof_signals_handled(self):
        """Context manager for exit signal handling."""
        signals = list(self.zof_config.exit_signals)
        for signum in signals:
            self.zof_loop.add_signal_handler(signum, self.zof_exit)

        yield

        for signum in signals:
            self.zof_loop.remove_signal_handler(signum)

    async def zof_invoke(self, event_type):
        """Notify app to start/stop."""
        logger.debug('Invoke %r', event_type)
        handler = self.zof_find_handler(event_type)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    def zof_find_handler(self, event_type):
        """Return handler function for given event type."""
        return getattr(self, 'on_%s' % event_type.lower(), None)

    def zof_exit(self, exit_status=0):
        """Exit controller event loop."""
        self.zof_exit_status.set_result(exit_status)

    def on_exception(self, exc):
        """Report exception from a zof handler function."""
        logger.critical('Exception in zof handler: %r', exc, exc_info=True)

    def on_channel_alert(self, dp, event):
        """Handle CHANNEL_ALERT message."""
        logger.warning('CHANNEL_ALERT dp=%r %r', dp, event)
