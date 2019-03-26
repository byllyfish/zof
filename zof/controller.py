"""Implements an OpenFlow Controller event dispatcher."""

from typing import Any, Dict, List, Tuple, Optional, Callable  # pylint: disable=unused-import

import asyncio
import contextlib
from contextvars import ContextVar

from zof.configuration import Configuration
from zof.datapath import Datapath
from zof.driver import Driver
from zof.log import logger, ZOFDEBUG
from zof.packet import Packet
from zof.tasklist import TaskList

EXIT_STATUS_OKAY = 0
EXIT_STATUS_ERROR = 10

_Event = Dict[str, Any]
_Handler = Callable[[Datapath, _Event], None]

_get_running_loop = getattr(asyncio, 'get_running_loop', asyncio.get_event_loop)
_current_task = getattr(asyncio, 'current_task', asyncio.Task.current_task)


class Controller:
    """Main dispatcher for OpenFlow events."""

    def __init__(self,
                 apps: Tuple[object, ...],
                 config: Optional[Configuration] = None):
        """Initialize controller with configuration object."""
        self.zof_config = config or Configuration()  # type: Configuration
        self.zof_driver = self.zof_config.zof_driver_class()  # type: Driver
        self.zof_connections = {}  # type: Dict[int, Datapath]
        self.zof_dpids = {}  # type: Dict[str, Datapath]
        self.zof_loop = None  # type: Optional[asyncio.AbstractEventLoop]
        self.zof_run_task = None  # type: Optional[asyncio.Task[Any]]
        self.zof_tasks = None  # type: Optional[TaskList]
        self.apps = apps  # type: Tuple[object, ...]
        self._handler_cache = {}  # type: Dict[str, _Handler]

    async def run(self) -> int:
        """Run controller in an event loop."""
        exit_status = EXIT_STATUS_OKAY
        with self.zof_run_context():
            async with self.zof_driver:
                try:
                    # Start app and OpenFlow listener.
                    await self.zof_invoke_lifecycle('START')
                    await self.zof_listen()

                    # Run until cancelled.
                    await self.zof_event_loop()

                    await self.zof_cleanup()
                    await self.zof_invoke_lifecycle('STOP')

                except Exception as ex:  # pylint: disable=broad-except
                    logger.critical('Exception in run: %r', ex, exc_info=True)
                    exit_status = EXIT_STATUS_ERROR

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

    def find_datapath(self, dp_id) -> Optional[Datapath]:
        """Retrieve the specified datapath, or None if not found.

        Returns:
            zof.Datapath

        """
        return self.zof_dpids.get(dp_id)

    def get_datapaths(self) -> List[Datapath]:
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
                    if dp is None:
                        continue  # datapath was force-closed
                else:
                    dp = self.zof_find_dp(event)
                    if dp is not None and dp.closed:
                        continue  # datapath was force-closed
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
        handlers = self.zof_find_handlers(event_type)
        if ZOFDEBUG:
            self._debug_receive(event_type, dp, event, handlers)

        for handler in handlers:
            try:
                handler(dp, event)
            except Exception as ex:  # pylint: disable=broad-except
                self.on_exception(ex)

    def _debug_receive(self, event_type, dp, event, handlers):
        """Log received event and associated handlers."""
        logger.debug('Receive %r %s xid=%s %r', dp, event_type,
                     event.get('xid'), handlers)
        if ZOFDEBUG >= 2:
            logger.debug(event)

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
        """Remove the zof Datapath object that represents the event source.

        If the datapath was already closed (using the force argument),
        return None.
        """
        conn_id = event['conn_id']
        dp = self.zof_connections.pop(conn_id)
        was_closed = dp.closed
        del self.zof_dpids[dp.id]
        dp.zof_cancel_tasks(self.zof_tasks)
        if was_closed:
            return None
        dp.closed = True
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
            if not dp.closed:
                dp.closed = True
                dp.zof_cancel_tasks(self.zof_tasks)
                self.zof_dispatch_event('CHANNEL_DOWN', dp, _channel_down())

        self.zof_tasks.cancel()
        await self.zof_tasks.wait_cancelled(3.0)

    @contextlib.contextmanager
    def zof_run_context(self):
        """Context manager for runtime state and signal handling."""
        ctxt_token = ZOF_CONTROLLER.set(self)
        self.zof_loop = _get_running_loop()
        self.zof_run_task = _current_task(self.zof_loop)
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
        ZOF_CONTROLLER.reset(ctxt_token)

    async def zof_invoke_lifecycle(self, event_type):
        """Notify apps to start/stop."""
        logger.debug('Invoke %r', event_type)
        handler_name = 'on_%s' % event_type.lower()
        for app in self.apps:
            handler = getattr(app, handler_name, None)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler()
                else:
                    handler()

    def zof_find_handlers(self, event_type):
        """Find list of handlers for given event type.

        Returns:
            Tuple of handler functions.

        """
        handler_name = 'on_%s' % event_type.lower()
        handlers = self._handler_cache.get(handler_name)
        if handlers is not None:
            # Return cached handler list.
            return handlers

        handlers = []
        for app in self.apps:
            handler = getattr(app, handler_name, None)
            if handler is not None:
                assert callable(handler)
                # Consider async handler support in the future.
                assert not asyncio.iscoroutinefunction(handler)
                handlers.append(handler)

        # Add default handler for channel_alert.
        if handler_name == 'on_channel_alert' and not handlers:
            handlers.append(self.on_channel_alert)

        # Save handler list in cache.
        handlers = tuple(handlers)
        self._handler_cache[handler_name] = handlers
        return handlers

    def zof_quit(self):
        """Quit controller event loop."""
        logger.debug('Request to cancel event loop')
        self.zof_run_task.cancel()

    def on_exception(self, exc):
        """Report exception from a zof handler function.

        Only the first `on_exception` handler is called. If
        there are no on_exception handlers, the default is to
        log the exception.
        """
        for app in self.apps:
            exc_handler = getattr(app, 'on_exception', None)
            if exc_handler:
                assert not asyncio.iscoroutinefunction(exc_handler)
                exc_handler(exc)
                break
        else:
            logger.critical('Exception in zof handler: %r', exc, exc_info=exc)

    def on_channel_alert(self, dp, event):  # pylint: disable=no-self-use
        """Handle CHANNEL_ALERT message."""
        logger.warning('CHANNEL_ALERT %r %r', dp, event)


def _channel_down():
    """Return a synthetic, minimal channel_down event."""
    return {'type': 'CHANNEL_DOWN'}


# ZOF_CONTROLLER is a context variable that returns the currently
# running controller instance.

ZOF_CONTROLLER = ContextVar('zof_controller')  # type: ContextVar[Controller]
