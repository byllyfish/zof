"""Implements Controller class."""

import asyncio
import logging
import sys
import functools
from collections import defaultdict
from .event import load_event, dump_event, make_event, Event
from .connection import Connection
from .run_server import run_server
from . import exception as _exc

_XID_TIMEOUT = 10.0  # Seconds
_IDLE_INTERVAL = 1.0
_MIN_XID = 8092
_MAX_XID = 0xFFFFFFFF
_API_VERSION = 0.9
_VERSION = '0.1.0'

LOGGER = logging.getLogger(__package__)


class Controller(object):
    """Concrete class that supports multiple app modules.

    Attributes:
        apps (List[ControllerApp]): List of apps ordered by precedence.
    """

    _singleton = None

    @staticmethod
    def singleton():
        """Return global singleton object."""
        if not Controller._singleton:
            Controller._singleton = Controller()
        return Controller._singleton

    @staticmethod
    def destroy():
        """Destroy global singleton object."""
        Controller._singleton = None

    def __init__(self):
        self.apps = []
        self._conn = None
        self._xid = _MIN_XID
        self._reqs = {}
        self._event_queue = None
        self._supported_versions = []
        self._tls_id = 0
        self._tasks = defaultdict(list)
        self._phase = 'INIT'

    def find_app(self, name):
        """Find application object by name."""
        return any(True for app in self.apps if app.name == name)

    def run_loop(self,
                 *,
                 listen_endpoints=None,
                 listen_versions=None,
                 oftr_options=None,
                 security=None):
        """Main entry point for running a controller."""
        if len(self.apps) == 0:
            LOGGER.warning('No apps are loaded.')

        try:
            asyncio.ensure_future(
                self._run(
                    listen_endpoints=listen_endpoints,
                    listen_versions=listen_versions,
                    oftr_options=oftr_options,
                    security=security))
            run_server(
                signals=['SIGTERM', 'SIGINT', 'SIGHUP'],
                signal_handler=self._handle_signal,
                logger=LOGGER)
            self._set_phase('POSTSTOP')

        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception(ex)

        finally:
            LOGGER.info('Exiting')

    def _handle_signal(self, signame):
        """Handle signals.

        Usually, signals indicate that the program should exit. An app can
        prevent shutdown by setting the event's `exit` value to False.
        """
        LOGGER.info('Signal Received: %s (qsize=%d)', signame,
                    self._event_queue.qsize())
        self.post_event(make_event(event='SIGNAL', signal=signame, exit=True))

    async def _run(self,
                   *,
                   listen_endpoints=None,
                   listen_versions=None,
                   oftr_options=None,
                   security=None):
        """Async task for running the controller."""
        LOGGER.debug("Controller._run entered")
        try:
            self._conn = Connection(oftr_options=oftr_options)
            await self._conn.connect()

            self._event_queue = asyncio.Queue()
            self._set_phase('PRESTART')

            asyncio.ensure_future(
                self._start(
                    listen_endpoints=listen_endpoints,
                    listen_versions=listen_versions,
                    security=security))
            asyncio.ensure_future(self._event_loop())
            idle = asyncio.ensure_future(self._idle_task())

            await self._read_loop()

            idle.cancel()
            self._set_phase('STOP')
            await self._conn.disconnect()

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._run')
            if self._conn:
                self._conn.close(False)
            asyncio.get_event_loop().stop()

        finally:
            LOGGER.debug("Controller._run exited")

    async def _event_loop(self):
        """Run the event loop to handle events."""
        try:
            LOGGER.debug('_event_loop entered')
            while True:
                event = await self._event_queue.get()
                self._dispatch_event(event)
                # If the event was dispatched to an async task, give it time
                # now to run so it can get started.
                await asyncio.sleep(0)
        except _exc.ExitException:
            self._conn.close(True)
            asyncio.get_event_loop().stop()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._event_loop')
            sys.exit(1)
        finally:
            LOGGER.debug('_event_loop exited')

    async def _read_loop(self):
        """Read messages from the driver and push them onto the event queue."""
        LOGGER.debug('_read_loop entered')
        running = True
        while running:
            line = await self._conn.readline()
            if line:
                self.post_event(load_event(line))
            else:
                LOGGER.debug('_read_loop: posting EXIT event')
                self.post_event(make_event(event='EXIT'))
                running = False
        LOGGER.debug('_read_loop exited')

    async def _start(self, *, listen_endpoints, listen_versions, security):
        """Configure the oftr driver based on controller arguments.

        This method runs concurrently with `run()`.
        """
        try:
            await self._get_description()
            if security:
                await self._configure_tls(security)
            if listen_endpoints:
                await self._listen_on_endpoints(listen_endpoints,
                                                listen_versions)
            self._set_phase('START')
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._start')
            self.post_event(make_event(event='STARTFAIL'))
            self.post_event(make_event(event='EXIT'))

    async def _get_description(self):
        """Check the api version used by oftr.

        Also, check the OpenFlow versions supported.
        """
        try:
            result = await self.rpc_call('OFP.DESCRIPTION')
            # Check API version.
            if float(result.api_version) != _API_VERSION:
                LOGGER.error('Unsupported API version %s', result.api_version)
                raise ValueError('Unsupported API version')

            self._supported_versions = result.versions
            LOGGER.info('Connected to oftr %s', result.sw_desc)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to get description from oftr %s', ex)
            raise

    async def _configure_tls(self, security):
        """Set up a TLS identity for connections to use."""
        try:
            result = await self.rpc_call(
                'OFP.ADD_IDENTITY',
                cert=security['cert'],
                cacert=security['cacert'],
                privkey=security['privkey'],
                password=security.get('password', ''))
            # Save tls_id from result so we can pass it in our calls to
            # 'OFP.LISTEN' and 'OFP.CONNECT'.
            self._tls_id = result.tls_id

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to create TLS identity: %s', ex.message)
            raise

    async def _listen_on_endpoints(self, listen_endpoints, listen_versions):
        """Listen on a list of endpoints."""
        assert isinstance(listen_endpoints, (list, tuple))
        options = ['FEATURES_REQ']
        versions = _prepare_versions(listen_versions, self._supported_versions)
        try:
            for endpt in listen_endpoints:
                result = await self.rpc_call(
                    'OFP.LISTEN',
                    endpoint=endpt,
                    versions=versions,
                    tls_id=self._tls_id,
                    options=options)
                LOGGER.info('Listening on %s [conn_id=%d, versions=%s]', endpt,
                            result.conn_id, versions)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to listen on %s: %s', endpt, ex.message)
            raise

    def post_event(self, event):
        """Post an event to our event queue."""
        assert isinstance(event, Event)
        self._event_queue.put_nowait(event)

    def _dispatch_event(self, event):
        """Dispatch an event we receive from the queue."""
        LOGGER.debug('_dispatch_event %r', event)
        try:
            if 'event' in event:
                self._handle_internal_event(event)
            elif 'id' in event:
                self._handle_rpc_reply(event)
            elif event.method == 'OFP.MESSAGE':
                type_ = event.params.type
                if not type_.startswith('CHANNEL_'):
                    self._handle_message(event)
                elif type_ == 'CHANNEL_ALERT':
                    self._handle_alert(event)
                else:
                    self._handle_channel(event)
            else:
                LOGGER.warning('Unhandled event: %r', event)
        except _exc.StopPropagationException:
            LOGGER.debug('_dispatch_event: StopPropagationException caught')

    def write(self, event, xid=None):
        """Write an event to the output stream.

        If `xid` is specified, return a `_ReplyFuture` to await the response.
        Otherwise, return None.
        """
        self._conn.write(dump_event(event))
        if xid is None:
            return

        # Register future to track the response.
        assert xid > 0
        fut = _ReplyFuture(xid)
        expiration = _timestamp() + _XID_TIMEOUT
        self._reqs[xid] = (fut, expiration, _XID_TIMEOUT)
        return fut

    def rpc_call(self, method, *, ignore_result=False, **params):
        """Send a RPC request and return a future for the reply.

        If ignore_result is True, issue the request but don't return the future.
        """
        if ignore_result:
            xid = None
            event = dict(method=method, params=params)
        else:
            xid = self.next_xid()
            event = dict(id=xid, method=method, params=params)
        LOGGER.debug('rpc_call %r', event)
        return self.write(event, xid)

    def _handle_xid(self, event, xid, except_class=None):
        """Lookup future associated with given xid and give it the event.

        If we find the future, but it has been cancelled, we still return True.

        Return False if no matching xid/future is found.
        """
        if xid not in self._reqs:
            return False

        fut = self._reqs[xid][0]
        if fut.cancelled():
            return True

        if except_class:
            fut.set_exception(except_class(event))
        else:
            fut.set_result(event)

        if not _event_has_more(event) or except_class:
            fut.set_done()
            del self._reqs[xid]

        return True

    def _handle_internal_event(self, event):
        """Called when an internal event is received."""
        # Immediately begin shutting down if there is an 'EXIT' event.
        if event.event == 'EXIT':
            raise _exc.ExitException()
        # Let apps handle the event.
        for app in self.apps:
            app.handle_event(event, 'event')
        # Check for SIGNAL event asking for exit.
        if event.event == 'SIGNAL' and event.exit:
            raise _exc.ExitException()

    def _handle_rpc_reply(self, event):
        """Called when a RPC reply is received."""
        if 'result' in event:
            result = event.result
            except_class = None
        else:
            result = event
            except_class = _exc.RPCException
        known_xid = self._handle_xid(result, event.id, except_class)
        if not known_xid:
            LOGGER.warning('Unrecognized id in RPC reply: %s', event)

    def _handle_message(self, event):
        """Called when a `OFP.MESSAGE` is received."""
        params = event.params
        if params.type == 'ERROR':
            except_class = _exc.ErrorException
        else:
            except_class = None
        # If the message does not have a datapath_id, don't attempt to handle
        # replies based on xid.
        known_xid = False
        if 'datapath_id' in params:
            known_xid = self._handle_xid(params, params.xid, except_class)

        if not known_xid:
            for app in self.apps:
                app.handle_event(params, 'message')
            # Log all OpenFlow error messages not associated with requests.
            if params.type == 'ERROR':
                LOGGER.error('ERROR: %s', params)

    def _handle_channel(self, event):
        """Called when `OFP.MESSAGE` is received with type 'CHANNEL_*'."""
        params = event.params
        scope_key = _make_scope_key(params.conn_id)
        # LOGGER.debug('_handle_channel: %s %s [conn_id=%s, version=%s]',
        #             scope_key, params.type, params.conn_id, params.version)

        if params.type == 'CHANNEL_DOWN':
            self._cancel_tasks(scope_key)

        for app in self.apps:
            app.handle_event(params, 'message')

    def _handle_alert(self, event):
        """Called when `OFP.MESSAGE` is received with type 'CHANNEL_ALERT'."""
        # First check if this alert was sent in response to something we said.
        params = event.params
        if params.xid and self._handle_xid(params, params.xid,
                                           _exc.DeliveryException):
            return
        # Otherwise, we need to report it.
        data = params.data.hex()
        if len(data) > 100:
            data = '%s...' % data[:100]
        LOGGER.warning(
            'Alert: %s data=%s (%d bytes) [conn_id=%s, datapath_id=%s, xid=%d]',
            params.alert, data,
            len(params.data), params.conn_id,
            params('datapath_id'), params.xid)

        for app in self.apps:
            app.handle_event(params, 'message')

    async def _idle_task(self):
        """Task to check for requests that have timed out."""
        while True:
            await asyncio.sleep(_IDLE_INTERVAL)
            now = _timestamp()
            timed_out = [
                (xid, fut, timeout)
                for (xid, (fut, expiration, timeout)) in self._reqs.items()
                if expiration <= now
            ]
            for xid, fut, timeout in timed_out:
                if not fut.cancelled():
                    fut.set_exception(_exc.TimeoutException(xid, timeout))
                del self._reqs[xid]

    def _set_phase(self, phase):
        """Called as the run loop changes phase:

            INIT -> PRESTART -> START -> STOP -> POSTSTOP.
        """
        LOGGER.debug('Change phase from "%s" to "%s"', self._phase, phase)
        if self._phase != 'PRESTART':
            self._cancel_tasks(self._phase)
        self._phase = phase
        event = make_event(event=phase)
        if phase in ('STOP', 'POSTSTOP'):
            self._dispatch_event(event)
        elif self._event_queue:
            self.post_event(event)

    def next_xid(self):
        """Return next xid to use.

        The controller reserves xid 0 and low numbered xid's.
        """

        if self._xid == _MAX_XID:
            self._xid = _MIN_XID
            return self._xid

        self._xid += 1
        return self._xid

    def ensure_future(self, coroutine, *, app, task_locals):
        """Run an async coroutine, within the scope of a specific scope_key.

        This function automatically captures exceptions from the coroutine. It
        also cleans up after the task when it is done.
        """

        @functools.wraps(coroutine)
        async def _capture_exception(coroutine):
            try:
                await coroutine
            except asyncio.CancelledError:
                app.logger.debug('ensure_future cancelled: %r', coroutine)
            except Exception:  # pylint: disable=broad-except
                app.handle_exception(None, scope_key)

        task = asyncio.ensure_future(_capture_exception(coroutine))
        conn_id = task_locals.get('conn_id')
        if conn_id:
            scope_key = _make_scope_key(conn_id)
        else:
            scope_key = self._phase
        self._tasks[scope_key].append(task)
        task.ofp_task_app = app
        task.ofp_task_scope = scope_key
        task.ofp_task_locals = task_locals
        task.add_done_callback(
            functools.partial(
                self._task_callback, scope_key=scope_key))
        return task

    def _cancel_tasks(self, scope_key):
        """Cancel async tasks associated with the given scope.

        The scope may be a datapath_id or a phase. The done callback removes the
        task from self._tasks.

        If scope_key is 'START' or 'STOP', cancel all tasks.
        """
        LOGGER.debug('_cancel_tasks: scope_key=%s, tasks=%r', scope_key,
                     self._tasks)
        if scope_key == 'START' or scope_key == 'STOP':
            for task_list in self._tasks.values():
                for task in task_list:
                    task.cancel()
        if scope_key in self._tasks:
            for task in self._tasks[scope_key]:
                LOGGER.debug('_cancel_task: %r', task)
                task.cancel()

    def _task_callback(self, task, scope_key):
        """Called when a scoped task is done.
        """
        # LOGGER.debug('_task_callback: %s[%s]', task, scope_key)
        tasks = self._tasks[scope_key]
        tasks.remove(task)
        if not tasks:
            del self._tasks[scope_key]


def _timestamp():
    """Return a monotonic timestamp in seconds."""
    return asyncio.get_event_loop().time()


def _event_has_more(event):
    try:
        return event.type.startswith('REPLY.') and 'MORE' in event.flags
    except AttributeError:
        return False


class _ReplyFuture:
    """
    Represents the Future-like object returned from OFP.request.

    For simple requests, use it with `await`:

      reply = await OFP.request(SOME_REQUEST, datapath_id=dpid)

    When expecting multiple replies, use it with `async for`:

      async for reply in OFP.request(SOME_REQUEST, datapath_id=dpid):
          process(reply)

    Alternatively, you can call `await` multiple times:

      multi_request = OFP.request(SOME_REQUEST, datapath_id=dpid)
      while not multi_request.done():
          reply = await multi_request
          process(reply)
    """

    def __init__(self, xid):
        self._xid = xid
        self._results = []
        self._future = None
        self._done = False

    def __del__(self):
        if self._results:
            LOGGER.warning('Multiple unread replies xid=%d: %s', self._xid,
                           self._results)

    def cancelled(self):
        return self._future and self._future.cancelled()

    def done(self):
        return not self._results and self._done

    def set_done(self):
        assert not self._done
        self._done = True

    def set_result(self, result):
        assert not isinstance(result, Exception)
        if self._future is None:
            self._results.append(result)
        else:
            self._future.set_result(result)
            self._future = None

    def set_exception(self, exc):
        assert isinstance(exc, Exception)
        if self._future is None:
            self._results.append(exc)
        else:
            self._future.set_exception(exc)
            self._future = None

    def __await__(self):
        """
        If there are existing results, return them immediately. Otherwise, if
        we are still expecting more results, return our future.
        """
        assert self._future is None
        if self._results:
            return _immediate_result(self._results.pop(0)).__await__()
        elif self._done:
            raise asyncio.InvalidStateError(
                'Called "await" too many times on _ReplyFuture')
        else:
            self._future = asyncio.Future()
            return self._future.__await__()

    async def __aiter__(self):
        return self

    async def __anext__(self):
        if self.done():
            raise StopAsyncIteration
        return await self


async def _immediate_result(result):
    if isinstance(result, Exception):
        raise result
    return result


def _make_scope_key(conn_id):
    return 'conn_id=%d' % conn_id


def _prepare_versions(listen_versions, supported_versions):
    """Return listen versions."""
    assert len(supported_versions) > 0
    if not listen_versions:
        return supported_versions
    # Check if any desired versions are unsupported.
    unsupported = set(listen_versions) - set(supported_versions)
    if len(unsupported) > 0:
        raise ValueError("Unsupported OpenFlow versions: %r" % unsupported)
    return listen_versions
