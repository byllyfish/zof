"""Implements a Controller base class."""

from typing import Any, Dict, List, Optional  # pylint: disable=unused-import

import asyncio
import contextlib
from contextvars import ContextVar

from zof.configuration import Configuration
from zof.datapath import Datapath
from zof.driver import Driver
from zof.log import logger
from zof.packet import Packet
from zof.tasklist import TaskList

EXIT_STATUS_OKAY = 0
EXIT_STATUS_ERROR = 10


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

    Methods and attributes that begin with `zof_` are reserved.

    """

    def __init__(self, config: Optional[Configuration] = None):
        """Initialize controller with configuration object."""
        self.zof_config = config or Configuration()  # type: Configuration
        self.zof_driver = self.zof_config.zof_driver_class()  # type: Driver
        self.zof_connections = {}  # type: Dict[int, Datapath]
        self.zof_dpids = {}  # type: Dict[str, Datapath]
        self.zof_loop = None  # type: Optional[asyncio.AbstractEventLoop]
        self.zof_run_task = None  # type: Optional[asyncio.Task[Any]]
        self.zof_tasks = None  # type: Optional[TaskList]

    async def run(self) -> int:
        """Run controller in an event loop."""
        exit_status = EXIT_STATUS_OKAY
        with self.zof_run_context():
            async with self.zof_driver:
                try:
                    # Start app and OpenFlow listener.
                    await self.zof_invoke('START')
                    await self.zof_listen()

                    # Run until cancelled.
                    await self.zof_event_loop()

                    await self.zof_cleanup()
                    await self.zof_invoke('STOP')

                except Exception as ex:  # pylint: disable=broad-except
                    logger.critical('Exception in run: %r', ex, exc_info=True)
                    exit_status = EXIT_STATUS_ERROR
                    await self.zof_cleanup()

        logger.debug('Exit status %d', exit_status)
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
        if self.zof_tasks is None:
            raise RuntimeError('Controller is not running.')
        return self.zof_tasks.create_task(coro)

    def get_config(self) -> Configuration:
        """Retrieve the configuration object.

        Returns:
            zof.Configuration

        """
        return self.zof_config

    def get_driver(self) -> Driver:
        """Retrieve the driver object.

        Returns:
            zof.Driver

        """
        return self.zof_driver

    def get_datapath(self, dp_id) -> Optional[Datapath]:
        """Retrieve the specified datapath, or None if not found.

        Returns:
            zof.Datapath

        """
        return self.zof_dpids.get(dp_id)

    def all_datapaths(self) -> List[Datapath]:
        """Retrieve a list of connected datapaths.

        Returns:
            List[zof.Datapath]

        """
        return list(self.zof_connections.values())

    async def zof_event_loop(self):
        """Dispatch events to handler functions.

        To exit the loop, cancel the task.
        """
        event_queue = self.zof_driver.event_queue

        while True:
            try:
                event = await event_queue.get()
                assert isinstance(event, dict), repr(event)
                event_type = event['type']

                # Update bookkeeping for connected datapaths.
                if event_type == 'CHANNEL_UP':
                    dp = self.zof_channel_up(event)
                elif event_type == 'CHANNEL_DOWN':
                    dp = self.zof_channel_down(event)
                else:
                    dp = self.zof_find_dp(event)
                    if event_type == 'PACKET_IN':
                        Packet.zof_from_packet_in(event)
                    elif event_type == 'PORT_STATUS':
                        dp.zof_from_port_status(event)

                # Dispatch event, then yield time to other tasks.
                self.zof_dispatch_event(event_type, dp, event)
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                logger.debug('Event loop cancelled')
                return

            except Exception as ex:  # pylint: disable=broad-except
                logger.critical(
                    'Exception in zof_event_loop: %r', ex, exc_info=True)

    def zof_dispatch_event(self, event_type, dp, event):
        """Dispatch event to a handler function."""
        handler = self.zof_find_handler(event_type)
        if handler:
            logger.debug('Dispatch %r %r', dp, event_type)
            try:
                handler(dp, event)
            except Exception as ex:  # pylint: disable=broad-except
                self.on_exception(ex)
        else:
            logger.debug('Dispatch %r %r (no handler)', dp, event_type)

    def zof_channel_up(self, event):
        """Add the zof Datapath object that represents the event source."""
        conn_id = event['conn_id']
        dp_id = int(event['datapath_id'].replace(':', ''), 16)
        assert conn_id not in self.zof_connections
        assert dp_id not in self.zof_dpids

        dp = Datapath(self, conn_id, dp_id)
        dp.zof_from_channel_up(event)
        self.zof_connections[conn_id] = dp
        self.zof_dpids[dp_id] = dp
        return dp

    def zof_channel_down(self, event):
        """Remove the zof Datapath object that represents the event source."""
        conn_id = event['conn_id']
        dp = self.zof_connections.pop(conn_id)
        del self.zof_dpids[dp.id]
        dp.closed = True
        dp.zof_cancel_tasks()
        return dp

    def zof_find_dp(self, event):
        """Find the zof Datapath object for the event source."""
        dp = None
        conn_id = event.get('conn_id')
        if conn_id is not None:
            dp = self.zof_connections.get(conn_id)
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
        for dp in self.zof_connections.values():
            dp.zof_cancel_tasks()

        self.zof_tasks.cancel()
        await self.zof_tasks.wait_cancelled()

    @contextlib.contextmanager
    def zof_run_context(self):
        """Context manager for runtime state and signal handling."""
        ctxt_token = _ZOF_CONTROLLER.set(self)
        self.zof_loop = asyncio.get_running_loop()
        self.zof_run_task = asyncio.current_task(self.zof_loop)
        self.zof_tasks = TaskList(self.zof_loop, self.on_exception)

        signals = list(self.zof_config.exit_signals)
        for signum in signals:
            self.zof_loop.add_signal_handler(signum, self.zof_quit)

        yield

        for signum in signals:
            self.zof_loop.remove_signal_handler(signum)

        self.zof_loop = None
        self.zof_run_task = None
        self.zof_tasks = None
        _ZOF_CONTROLLER.reset(ctxt_token)

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

    def zof_quit(self):
        """Quit controller event loop."""
        self.zof_run_task.cancel()

    def on_exception(self, exc):  # pylint: disable=no-self-use
        """Report exception from a zof handler function."""
        logger.critical('Exception in zof handler: %r', exc, exc_info=exc)

    def on_channel_alert(self, dp, event):  # pylint: disable=no-self-use
        """Handle CHANNEL_ALERT message."""
        logger.warning('CHANNEL_ALERT dp=%r %r', dp, event)


# _ZOF_CONTROLLER is a context variable that returns the currently
# running controller instance.

_ZOF_CONTROLLER = ContextVar('zof_controller')  # type: ContextVar[Controller]


def get_controller() -> Controller:
    """Return currently running controller instance."""
    return _ZOF_CONTROLLER.get()
