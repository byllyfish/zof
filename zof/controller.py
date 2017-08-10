"""Implements Controller class."""

import asyncio
import logging
import sys
import functools
import inspect
from collections import defaultdict
from .event import load_event, dump_event, make_event, Event
from .objectview import make_objectview
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
        args (argparse.Namespace): Arguments parsed by argparse module.
        phase (str): Lifecycle phase.
        conn (Connection): oftr connection
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
        self.args = None
        self.phase = 'INIT'
        self.conn = None
        self._xid = _MIN_XID
        self._reqs = {}
        self._event_queue = None
        self._supported_versions = []
        self._tls_id = 0
        self._tasks = defaultdict(list)
        self._exit_status = 1

    def find_app(self, name):
        """Find application object by name."""
        return any(app for app in self.apps if app.name == name)

    def run_loop(self, *, args):
        """Main entry point for running a controller.

        Returns exit status.
        """
        if not self.apps:
            LOGGER.warning('No apps are loaded.')

        self.args = make_objectview(args)

        try:
            asyncio.ensure_future(self._run())
            run_server(
                signals=['SIGTERM', 'SIGINT', 'SIGHUP'],
                signal_handler=self._handle_signal,
                logger=LOGGER)
            self._set_phase('POSTSTOP')

        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception(ex)

        finally:
            # Log a warning if there are any asyncio tasks still present.
            task_count = len(asyncio.Task.all_tasks())
            if task_count > 0:
                LOGGER.warning('run_loop: Exiting with %d tasks!', task_count)
            LOGGER.info('Exiting with status %d', self._exit_status)

        return self._exit_status

    def _handle_signal(self, signame):
        """Handle signals.

        Usually, signals indicate that the program should exit. An app can
        prevent shutdown by setting the event's `exit` value to False.
        """
        LOGGER.info('Signal Received: %s (qsize=%d)', signame,
                    self._event_queue.qsize())
        self.post_event(make_event(event='SIGNAL', signal=signame, exit=True))

    async def _run(self):
        """Async task for running the controller."""
        LOGGER.debug("Controller._run entered")
        try:
            self._preflight()

            self.conn = Connection(oftr_options={
                'path': self.args('x_oftr_path'),
                'args': self.args('x_oftr_args'),
                'prefix': self.args('x_oftr_prefix')
            })
            await self.conn.connect()

            self._event_queue = asyncio.Queue()
            self._set_phase('PRESTART')

            asyncio.ensure_future(self._start())
            asyncio.ensure_future(self._read_loop())
            idle = asyncio.ensure_future(self._idle_task())

            await self._event_loop()

            idle.cancel()
            self._set_phase('STOP')
            await self.conn.disconnect()

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._run')
            if self.conn:
                self.conn.close(False)
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
        except _exc.ExitException as ex:
            self._exit_status = ex.exit_status
            self.conn.close(True)
            asyncio.get_event_loop().stop()
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._event_loop')
            sys.exit(1)
        finally:
            LOGGER.debug('_event_loop exited')

    async def _read_loop(self):
        """Read messages from the driver and push them onto the event queue.

        TODO(bfish): Could be implemented as a lower-level Protocol via
        Connection class.
        """
        LOGGER.debug('_read_loop entered')
        while True:
            line = await self.conn.readline()
            if not line:
                break
            self.post_event(load_event(line))
        LOGGER.debug('_read_loop exited')

    async def _start(self):
        """Configure the oftr driver based on controller arguments.

        This method runs concurrently with `run()`.
        """
        try:
            await self._get_description()
            if self.args.listen_cert:
                await self._configure_tls()
            if self.args.listen_endpoints:
                await self._listen_on_endpoints()
            # TODO(bfish): Wait for other prestart tasks to finish.
            self._set_phase('START')
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Exception in Controller._start')
            self.post_event(make_event(event='STARTFAIL'))
            self.post_event(make_event(event='EXIT', exit_status=11))

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

    async def _configure_tls(self):
        """Set up a TLS identity for connections to use."""
        try:
            result = await self.rpc_call(
                'OFP.ADD_IDENTITY',
                cert=self.args.listen_cert,
                cacert=self.args.listen_cacert,
                privkey=self.args.listen_privkey)
            # Save tls_id from result so we can pass it in our calls to
            # 'OFP.LISTEN' and 'OFP.CONNECT'.
            self._tls_id = result.tls_id

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to create TLS identity: %s', ex.message)
            raise

    async def _listen_on_endpoints(self):
        """Listen on a list of endpoints."""
        listen_endpoints = self.args.listen_endpoints
        listen_versions = self.args.listen_versions
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
        if not isinstance(event, Event):
            raise ValueError('Not an event: %r' % event)
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
                self._handle_message(event.params)
            else:
                LOGGER.warning('Unhandled event: %r', event)
        except _exc.StopPropagationException:
            LOGGER.debug('_dispatch_event: StopPropagationException caught')

    def write(self, event, xid=None):
        """Write an event to the output stream.

        If `xid` is specified, return a `_ReplyFuture` to await the response.
        Otherwise, return None.
        """
        self.conn.write(dump_event(event))
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
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug('rpc_call %r', _sanitize_rpc(event))
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
        if event.event == 'MESSAGE':
            self._handle_message(event)
            return
        # Immediately begin shutting down if there is an 'EXIT' event.
        if event.event == 'EXIT':
            raise _exc.ExitException(event('exit_status', default=0))
        # Let apps handle the event.
        for app in self.apps:
            app.handle_event(event, 'event')
        # Check for SIGNAL event asking for exit.
        if event.event == 'SIGNAL' and event.exit:
            raise _exc.ExitException(_negative_signal_number(event.signal))

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

    def _handle_message(self, message):
        """Called when a `OFP.MESSAGE` is received."""
        msg_type = message.type
        if msg_type.startswith('CHANNEL_'):
            self._handle_channel(message)
            return
        if msg_type == 'ERROR':
            except_class = _exc.ErrorException
        else:
            except_class = None
        # If the message does not have a datapath_id, don't attempt to handle
        # replies based on xid.
        known_xid = False
        if 'datapath_id' in message:
            known_xid = self._handle_xid(message, message.xid, except_class)

        if not known_xid:
            for app in self.apps:
                app.handle_event(message, 'message')
            # Log all OpenFlow error messages not associated with requests.
            if msg_type == 'ERROR':
                LOGGER.error('ERROR: %s', message)

    def _handle_channel(self, message):
        """Called when `OFP.MESSAGE` is received with type 'CHANNEL_*'."""
        if message.type == 'CHANNEL_ALERT':
            self._handle_alert(message)
            return
        if message.type == 'CHANNEL_DOWN':
            scope_key = _make_scope_key(message.conn_id)
            self._cancel_tasks(scope_key)
        for app in self.apps:
            app.handle_event(message, 'message')

    def _handle_alert(self, message):
        """Called when `OFP.MESSAGE` is received with type 'CHANNEL_ALERT'."""
        # First check if this alert was sent in response to something we said.
        if message.xid and self._handle_xid(message, message.xid,
                                            _exc.DeliveryException):
            return
        # Otherwise, we need to report it.
        data = message.data.hex()
        if len(data) > 100:
            data = '%s...' % data[:100]
        LOGGER.warning(
            'Alert: %s data=%s (%d bytes) [conn_id=%s, datapath_id=%s, xid=%d]',
            message.alert, data,
            len(message.data), message.conn_id,
            message('datapath_id'), message.xid)

        for app in self.apps:
            app.handle_event(message, 'message')

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
        LOGGER.debug('Change phase from "%s" to "%s"', self.phase, phase)
        if self.phase != 'PRESTART':
            self._cancel_tasks(self.phase)
        self.phase = phase
        event = make_event(event=phase)
        if phase in ('STOP', 'POSTSTOP'):
            self._dispatch_event(event)
        elif self._event_queue:
            self.post_event(event)

    def _preflight(self):
        """Called at the end of the INIT phase.
        """
        event = make_event(event='PREFLIGHT')
        for app in list(self.apps):
            try:
                app.handle_event(event, 'event')
            except _exc.PreflightUnloadException:
                self.apps.remove(app)
            except Exception:  # pylint: disable=broad-except
                app.handle_exception(event, 'event')

    def next_xid(self):
        """Return next xid to use.

        The controller reserves xid 0 and low numbered xid's.
        """

        if self._xid == _MAX_XID:
            self._xid = _MIN_XID
            return self._xid

        self._xid += 1
        return self._xid

    def ensure_future(self, coroutine, *, app=None, datapath_id, conn_id):
        """Run an async coroutine, within the scope of a specific scope_key.

        This function automatically captures exceptions from the coroutine. It
        also cleans up after the task when it is done.
        """

        @functools.wraps(coroutine)
        async def _capture_exception(coroutine):
            try:
                await coroutine
            except asyncio.CancelledError:
                LOGGER.debug('ensure_future cancelled: %r', coroutine)
            except Exception:  # pylint: disable=broad-except
                if app:
                    app.handle_exception(None, scope_key)
                else:
                    LOGGER.error('Exception caught', exc_info=True)

        assert inspect.isawaitable(coroutine)
        task_locals = dict(datapath_id=datapath_id, conn_id=conn_id)
        task = asyncio.ensure_future(_capture_exception(coroutine))
        conn_id = task_locals.get('conn_id')
        if conn_id:
            scope_key = _make_scope_key(conn_id)
        else:
            scope_key = self.phase
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
    assert supported_versions
    if not listen_versions:
        return supported_versions
    # Check if any desired versions are unsupported.
    unsupported = set(listen_versions) - set(supported_versions)
    if unsupported:
        raise ValueError("Unsupported OpenFlow versions: %r" % unsupported)
    return listen_versions


def _sanitize_rpc(event):
    """Sanitize certain RPC events before logging them."""
    if event['method'] == 'OFP.ADD_IDENTITY':
        event = event.copy()
        event['params'] = event['params'].copy()
        event['params']['privkey'] = '*** ELIDED ***'
    return event


def _negative_signal_number(signame):
    """Return negative number to represent signal named `signame`.

    If signame is unknown, return -99.
    """
    try:
        import signal
        return -getattr(signal, signame)
    except AttributeError:
        return -99
