"""Implements Controller class."""

import asyncio
import logging
import re
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

LOGGER = logging.getLogger('pylibofp')


class Controller(object):
    """Concrete class that supports multiple app modules.

    Attributes:
        apps (List[ControllerApp]): List of apps.
    """

    _singleton = None

    @staticmethod
    def singleton():
        """Return global singleton object."""
        if not Controller._singleton:
            Controller._singleton = Controller()
        return Controller._singleton

    def __init__(self):
        self.apps = []
        self._conn = None
        self._xid = _MIN_XID
        self._reqs = {}
        self._event_queue = None
        self._ofp_versions = []
        self._tls_id = 0
        self._tasks = defaultdict(list)
        self._phase = 'INIT'

    def run_loop(self, *, listen_endpoints=None, oftr_args=None,
                 security=None):
        """Main entry point for running a controller.
        """
        try:
            asyncio.ensure_future(
                self._run(
                    listen_endpoints=listen_endpoints,
                    oftr_args=oftr_args,
                    security=security))

            LOGGER.debug('run_server started')
            run_server(
                signals=['SIGTERM', 'SIGINT', 'SIGHUP'],
                signal_handler=self._handle_signal)
            LOGGER.debug('run_server stopped')
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
        LOGGER.info('Signal Received: %s', signame)
        self.post_event(make_event(event='SIGNAL', signal=signame, exit=True))

    async def _run(self,
                   *,
                   listen_endpoints=None,
                   oftr_args=None,
                   security=None):
        """Async task for running the controller.
        """

        LOGGER.debug("Controller._run entered")
        try:
            self._conn = Connection(oftr_args=oftr_args)
            await self._conn.connect()

            self._event_queue = asyncio.Queue()
            self._set_phase('PRESTART')

            asyncio.ensure_future(
                self._start(
                    listen_endpoints=listen_endpoints, security=security))
            asyncio.ensure_future(self._event_loop())
            idle = asyncio.ensure_future(self._idle_task())

            await self._read_loop()

            idle.cancel()
            self._set_phase('STOP')
            await self._conn.disconnect()

        except Exception:    # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._run')
            if self._conn:
                self._conn.close(False)
            asyncio.get_event_loop().stop()

        finally:
            LOGGER.debug("Controller._run exited")

    async def _event_loop(self):
        """Run the event loop to handle events.
        """
        try:
            LOGGER.debug('_event_loop entered')
            while True:
                event = await self._event_queue.get()
                self._dispatch_event(event)

        except _exc.ExitException:
            self._conn.close(True)
            asyncio.get_event_loop().stop()
        finally:
            LOGGER.debug('_event_loop exited')

    async def _read_loop(self):
        """Read messages from the driver and push them onto the event queue.
        """
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

    async def _start(self, *, listen_endpoints, security):
        """Configure the oftr driver based on controller arguments.

        This method runs concurrently with `run()`.
        """

        try:
            await self._get_description()
            if security:
                await self._configure_tls(security)
            if listen_endpoints:
                await self._listen_on_endpoints(listen_endpoints)

            self._set_phase('START')

        except _exc.ControllerException:
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

            self._ofp_versions = result.versions
            LOGGER.info('Connected to oftr %s', result.sw_desc)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to get description from oftr %s', ex)
            raise

    async def _configure_tls(self, security):
        """Set up a TLS identity for connections to use.
        """
        try:
            result = await self.rpc_call(
                'OFP.ADD_IDENTITY',
                certificate=security['cert'],
                verifier=security['cafile'],
                password=security.get('password', ''))
            # Save tls_id from result so we can pass it in our calls to
            # 'OFP.LISTEN' and 'OFP.CONNECT'.
            self._tls_id = result.params.tls_id

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to create TLS identity: %s', ex.message)
            raise

    async def _listen_on_endpoints(self, listen_endpoints):
        """Listen on a list of endpoints.
        """
        ofversion = None  # TODO: replace self._config.ofversion
        options = ['FEATURES_REQ']
        if not ofversion:
            ofversion = self._ofp_versions
        try:
            for endpt in listen_endpoints:
                result = await self.rpc_call(
                    'OFP.LISTEN',
                    endpoint=endpt,
                    versions=ofversion,
                    tls_id=self._tls_id,
                    options=options)
                LOGGER.info('Listening on %s [conn_id=%d, versions=%s]', endpt,
                            result.conn_id, ofversion)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to listen on %s: %s', endpt, ex.message)
            raise

    def post_event(self, event):
        """Post an event to our event queue.
        """
        assert isinstance(event, Event)
        self._event_queue.put_nowait(event)

    def _dispatch_event(self, event):
        """Dispatch an event we receive from oftr.
        """
        LOGGER.debug('_dispatch_event %r', event)

        try:
            if 'event' in event:
                self._handle_internal_event(event)
            elif 'id' in event:
                self._handle_rpc_reply(event)
            elif event.method == 'OFP.MESSAGE':
                type_ = event.params.type
                if not type_.startswith('CHANNEL_'):
                    self._handle_message(event.params)
                elif type_ == 'CHANNEL_ALERT':
                    self._handle_alert(event.params)
                else:
                    self._handle_channel(event.params)
            else:
                LOGGER.warning('Unhandled event: %r', event)
        except _exc.BreakException:
            LOGGER.debug('_dispatch_event: BreakException caught')

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
        self._reqs[xid] = (fut, expiration)
        return fut

    def rpc_call(self, method, **params):
        """Send a RPC request and return a future for the reply.
        """

        LOGGER.debug('rpc_call %s', method)
        xid = self.next_xid()
        event = dict(id=xid, method=method, params=params)
        return self.write(event, xid)

    def _handle_xid(self, event, xid, except_class=None):
        """Lookup future associated with given xid and give it the event.

        Return False if no matching xid is found.
        """

        if xid not in self._reqs:
            return False

        fut, _ = self._reqs[xid]
        if except_class:
            fut.set_exception(except_class(event))
        else:
            fut.set_result(event)

        if not _event_has_more(event) or except_class:
            fut.set_done()
            del self._reqs[xid]

        return True

    def _handle_internal_event(self, event):
        """Called when an internal event is received.
        """
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
        """Called when a RPC reply is received.
        """
        if 'result' in event:
            result = event.result
            except_class = None
        else:
            result = event
            except_class = _exc.RPCException
        if not self._handle_xid(result, event.id, except_class):
            LOGGER.warning('Unrecognized id in RPC reply: %s', event)

    def _handle_message(self, params):
        """Called when a `OFP.MESSAGE` is received.
        """
        if params.type == 'ERROR':
            except_class = _exc.ErrorException
        else:
            except_class = None

        if not self._handle_xid(params, params.xid, except_class):
            for app in self.apps:
                app.handle_event(params, 'message')
            # Log all OpenFlow error messages not associated with requests.
            if params.type == 'ERROR':
                LOGGER.error('ERROR: %s', params)

    def _handle_channel(self, params):
        """Called when a `OFP.MESSAGE` is received with type 'CHANNEL_*'.
        """
        dpid = params('datapath_id')
        if dpid:
            scope_key = 'Datapath %s' % dpid
        else:
            scope_key = 'Channel %s' % params.conn_id

        LOGGER.debug('_handle_channel: %s %s [conn_id=%s, version=%s]', 
                     scope_key, params.type, params.conn_id, params.version)

        if params.type == 'CHANNEL_DOWN':
            self._cancel_tasks(scope_key)

        for app in self.apps:
            app.handle_event(params, 'message')

    def _handle_alert(self, params):
        """Called when `OFP.MESSAGE` is received with type 'CHANNEL_ALERT'.
        """
        # First check if this alert was sent in response to something we said.
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
        """Task to check for requests that have timed out.
        """
        while True:
            await asyncio.sleep(_IDLE_INTERVAL)
            now = _timestamp()
            timed_out = [(xid, fut)
                         for (xid, (fut, expiration)) in self._reqs.items()
                         if expiration <= now]
            for xid, fut in timed_out:
                fut.set_exception(_exc.TimeoutException(xid))
                del self._reqs[xid]

    def _set_phase(self, phase):
        """Called as the run loop changes phase:

            INIT -> PRESTART -> START -> STOP -> POSTSTOP.
        """
        LOGGER.debug('Change phase from "%s" to "%s"', self._phase, phase)
        if self._phase != 'PRESTART':
            self._cancel_tasks(self._phase)
        self._phase = phase
        if self._event_queue:
            self.post_event(make_event(event=phase))

    def next_xid(self):
        """Return next xid to use.

        The controller reserves xid 0 and low numbered xid's.
        """

        if self._xid == _MAX_XID:
            self._xid = _MIN_XID
            return self._xid

        self._xid += 1
        return self._xid

    def ensure_future(self, coroutine, *, scope_key=None, app, task_locals):
        """Run an async coroutine, within the scope of a specific scope_key.

        This function automatically captures exceptions from the coroutine. It
        also cleans up after the task when it is done.
        """

        @functools.wraps(coroutine)
        async def _capture_exception(coroutine):
            try:
                app.logger.debug('ensure_future: %s', _coro_name(coroutine))
                await coroutine
                app.logger.debug('ensure_future done: %s',
                                 _coro_name(coroutine))
            except asyncio.CancelledError:
                app.logger.debug('ensure_future cancelled: %s',
                                 _coro_name(coroutine))
            except Exception:  # pylint: disable=broad-except
                app.handle_exception(None, scope_key)

        task = asyncio.ensure_future(_capture_exception(coroutine))
        if not scope_key:
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
        LOGGER.debug('_cancel_tasks: scope_key=%s', scope_key)
        if scope_key == 'START' or scope_key == 'STOP':
            for task_list in self._tasks.values():
                for task in task_list:
                    task.cancel()
        if scope_key in self._tasks:
            for task in self._tasks[scope_key]:
                task.cancel()

    def _task_callback(self, task, scope_key):
        """Called when a scoped task is done.
        """
        LOGGER.debug('_task_callback: %s[%s]', task, scope_key)
        self._tasks[scope_key].remove(task)


def _timestamp():
    """Return a monotonic timestamp in seconds.
    """
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


_COROUTINE_REGEX = re.compile(
    r'^<CoroWrapper (\S+)(?: running at | done, defined at )([^,]+),')


def _coro_name(coroutine):
    """
    Return short string describing the coroutine, e.g. "init() some_file:34".
    """
    result = repr(coroutine)
    m = _COROUTINE_REGEX.match(result)
    if m:
        result = '%s %s' % m.group(1, 2)
    return result
