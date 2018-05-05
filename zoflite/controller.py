from zoflite.driver import Driver
from zoflite.datapath import Datapath
from zoflite.taskset import TaskSet
import asyncio
import logging
import signal


LOGGER = logging.getLogger(__package__)


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
        asyncio.get_event_loop().run_until_complete(HubController().run())

    """

    zof_driver = None
    zof_loop = None
    zof_listen_endpoints = ['6653']
    zof_listen_options = ['FEATURES_REQ']
    zof_listen_versions = []
    zof_datapaths = None
    zof_exit_status = None
    zof_exit_signals = [signal.SIGTERM, signal.SIGINT]
    zof_tasks = None

    async def run(self):
        """Run controller in an event loop."""

        if self.zof_driver is None:
            self.zof_driver = Driver(self.zof_dispatch)
        else:
            # Set dispatch function of existing driver; this is used
            # for testing with a mock driver.
            assert self.zof_driver.dispatch is None
            self.zof_driver.dispatch = self.zof_dispatch

        self.zof_loop = asyncio.get_event_loop()
        self.zof_exit_status = self.zof_loop.create_future()
        self.zof_datapaths = {}
        self.zof_tasks = TaskSet(self.zof_loop)

        self.zof_init_signals()

        async with self.zof_driver:
            # Make sure the DRIVER_UP event is dispatched first.
            await asyncio.sleep(0)

            # Start app and OpenFlow listener.
            await self.zof_invoke('START')
            await self.zof_listen()

            # Run until we're told to exit.
            await self.zof_exit_status

            # Clean up after ourselves.
            self.zof_tasks.cancel()
            await self.zof_tasks.wait_cancelled()
            await self.zof_invoke('STOP')

        # Dispatch DRIVER_DOWN event before returning.
        await asyncio.sleep(0)

    def create_task(self, coro):
        """Create a managed async task."""

        self.zof_tasks.create_task(coro)

    def zof_dispatch(self, _driver, event):
        """Dispatch incoming event to an app handler.

        N.B. The handler is scheduled to run on the event loop. This function
        returns immediately.
        """

        # TODO(bfish): change oftr dsl.
        msg_type = event['type'].replace('.', '_')

        dp = None
        if msg_type == 'CHANNEL_UP':
            dp = self.zof_channel_up(event)
        elif msg_type == 'CHANNEL_DOWN':
            dp = self.zof_channel_down(event)

        handler = getattr(self, msg_type, None)
        if handler:
            if dp is None:
                dp = self.zof_find_dp(event)

            if asyncio.iscoroutinefunction(handler):
                if dp:
                    dp.create_task(handler(dp, event))
                else:
                    raise RuntimeError('No datapath object for async task')
            else:
                self.zof_loop.call_soon(handler, dp, event)

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

        if self.zof_listen_endpoints:
            coros = [self.zof_driver.listen(endpoint, options=self.zof_listen_options, versions=self.zof_listen_versions) for endpoint in self.zof_listen_endpoints]
            await asyncio.gather(*coros)

    def zof_init_signals(self):
        """Set up exit signal handler."""

        def _quit():
            self.zof_exit(0)

        for signum in self.zof_exit_signals:
            self.zof_loop.add_signal_handler(signum, _quit)

    async def zof_invoke(self, name):
        """Notify app to start/stop.

        N.B. The handler is invoked directly from the current task.
        """

        handler = getattr(self, name, None)
        if not handler:
            return

        if asyncio.iscoroutinefunction(handler):
            await handler()
        else:
            handler()

    def zof_exit(self, exit_status):
        """Exit controller event loop."""

        self.zof_exit_status.set_result(exit_status)

    def CHANNEL_ALERT(self, dp, event):
        """Default handler for CHANNEL_ALERT message."""

        LOGGER.error('CHANNEL_ALERT received: %r', event)
