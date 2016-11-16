import asyncio
import logging
import os
import sys
import re
import signal
import functools
from collections import defaultdict
from pylibofp.event import load_event, dump_event, make_event
from pylibofp.config import load_config
from pylibofp.controllerapp import ControllerApp
from pylibofp.connection import Connection
from pylibofp.objectview import ObjectView
import pylibofp.exception as _exc

_XID_TIMEOUT = 10.0  # Seconds
_IDLE_INTERVAL = 1.0
_MIN_XID = 8092
_MAX_XID = 0xFFFFFFFF
_API_VERSION = 1
_VERSION = '0.1.0'

LOGGER = logging.getLogger('pylibofp.controller')


def run(config_file=None, relative_to=None):
    """
    Convenience function for running a controller.
    """
    if relative_to:
        directory = os.path.dirname(os.path.abspath(relative_to))
        config_file = os.path.join(directory, config_file)

    controller = Controller(config_file=config_file, arguments=sys.argv[1:])
    controller.run_loop()
    LOGGER.info('Exiting')


class Controller(object):
    """
    Concrete class representing an OpenFlow controller that supports multiple
    app modules.
    """

    def __init__(self, *, config_file, arguments=None):
        """
        Initialize controller from the specified configuration file.
        """

        # Clear default event_loop; async tasks are forbidden during INIT and
        # PRESTART phases.
        asyncio.set_event_loop(None)
        self._phase = 'INIT'

        self._config = load_config(
            config_file=config_file, arguments=arguments)
        LOGGER.info('Pylibofp %s, Python %s', _VERSION, sys.version.split()[0])

        self._conn = Connection(libofp_args=self._config.libofp)
        self._xid = _MIN_XID
        self._reqs = {}
        self._idle_task = None
        self._event_queue = None
        self._shared = ObjectView({})
        self._datapaths = set()
        self._ofp_versions = []
        self._tasks = defaultdict(list)
        self._set_phase('PRESTART')
        self._apps = [ControllerApp(self, name) for name in self._config.apps]

    def run_loop(self):
        """
        Main entry point for running a controller.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._add_signal_handlers(loop, ('SIGTERM', 'SIGINT'))
        LOGGER.debug('asyncio loop started')
        try:
            loop.run_until_complete(self._run())
        except KeyboardInterrupt:
            # Shutdown cleanly when we get an interrupt.
            self._shutdown_cleanly(loop)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        LOGGER.debug('asyncio loop stopped')

    def _add_signal_handlers(self, loop, signals):
        """
        Add signal handlers to the event loop.

        We use a KeyboardInterrupt to signal it's time to shutdown.
        """

        def handle_signal(signame):
            LOGGER.info('Signal Received: %s', signame)
            raise KeyboardInterrupt

        for signame in signals:
            loop.add_signal_handler(
                getattr(signal, signame),
                functools.partial(handle_signal, signame))

    def _shutdown_cleanly(self, loop):
        """
        Give existing tasks a chance to complete.
        """
        try:
            self._post_event(make_event(event='EXIT'))

            # Try 3 times to finish our pending tasks.
            for i in range(3):
                if not self._run_pending(loop, timeout=5.0):
                    break

        except Exception as ex:  # pylint: disable=broad-except
            LOGGER.exception(ex)
        finally:
            self._set_phase('POSTSTOP')

    def _run_pending(self, loop, timeout=None):
        """
        Run until pending tasks are complete. Return true if we still have
        pending tasks when the pending tasks complete.
        """
        try:
            pending = asyncio.Task.all_tasks()
            LOGGER.debug('Waiting for %d pending tasks', len(pending))
            loop.run_until_complete(asyncio.wait(pending, timeout=timeout))
            return False
        except RuntimeError as ex:
            # `run_until_complete` throws an exception if new async tasks are
            # started by the pending tasks. Return true when this happens.
            if str(ex) == 'Event loop stopped before Future completed.':
                return True
            raise

    @property
    def config(self):
        """
        Return the controller's configuration object.
        """
        return self._config

    @property
    def shared(self):
        """
        Return the controller's shared object.
        """
        return self._shared

    @property
    def datapaths(self):
        """
        Return list of datapath id's.
        """
        return self._datapaths

    async def _run(self):
        """
        Run the controller within asyncio.
        """

        LOGGER.debug("Controller.run entered")

        self._idle_task = asyncio.get_event_loop().call_later(_IDLE_INTERVAL,
                                                              self._idle)
        self._event_queue = asyncio.Queue()

        await self._conn.connect()
        self._set_phase('START')
        self._dispatch_event(make_event(event='START'))

        asyncio.ensure_future(self._start())
        asyncio.ensure_future(self._event_loop())

        await self._read_loop()
        # FIXME: handle case where _read_loop finishes first.

        self._set_phase('STOP')
        self._dispatch_event(make_event(event='STOP'))
        await self._conn.disconnect()

        self._idle_task.cancel()
        self._event_queue = None

        LOGGER.debug("Controller.run exited")

    async def _event_loop(self):
        """
        Run the event loop to handle events.
        """

        LOGGER.debug('_event_loop entered')
        try:
            while True:
                event = await self._event_queue.get()
                self._dispatch_event(event)

        except _exc.ExitException:
            self._conn.close()
        LOGGER.debug('_event_loop exited')

    async def _read_loop(self):
        """
        Read messages from the driver and push them onto the event queue.
        """

        LOGGER.debug('_read_loop entered')
        running = True
        while running:
            line = await self._conn.readline()
            if line:
                self._post_event(load_event(line))
            else:
                LOGGER.debug('_read_loop: posting EXIT event')
                self._post_event(make_event(event='EXIT'))
                running = False

        LOGGER.debug('_read_loop exited')

    async def _start(self):
        """
        Configure the libofp driver based on controller arguments.
        This method runs concurrently with `run()`.
        """

        try:
            await self._get_description()

            if self._config.cert:
                await self._configure_tls()

            await self._listen_on_endpoints()
            await self._connect_to_endpoints()

            self._post_event(make_event(event='READY'))

        except _exc.ControllerException:
            self._post_event(make_event(event='STARTFAIL'))
            self._post_event(make_event(event='EXIT'))

    async def _get_description(self):
        """
        Check the api version used by libofp. Also, check the OpenFlow versions
        supported.
        """
        try:
            result = await self._rpc_call('OFP.DESCRIPTION')
            # Check major API version.
            if result.major_version > _API_VERSION:
                LOGGER.error('Unsupported API version %d.%d',
                             result.major_version, result.minor_version)
                raise ValueError('Unsupported API version')

            self._ofp_versions = result.ofp_versions
            LOGGER.info('Connected to libofp %s', result.software_version)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to get description from libofp %s', ex)
            raise

    async def _configure_tls(self):
        """
        Set up a TLS identity for connections to use.
        """
        try:
            result = await self._rpc_call(
                'OFP.ADD_IDENTITY',
                certificate=self._config.cert,
                verifier=self._config.cafile,
                password=self._config.password)
            # Save tls_id from result in config object so we can pass it in
            # our calls to 'OFP.LISTEN' and 'OFP.CONNECT'.
            self._config.tls_id = result.params.tls_id

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to create TLS identity: %s', ex.message)
            raise

    async def _listen_on_endpoints(self):
        """
        Listen on a list of endpoints.
        """
        tls_id = self._config.tls_id
        ofversion = self._config.ofversion
        options = self._config.listen_options
        if not ofversion:
            ofversion = self._ofp_versions
        try:
            for endpt in self._config.listen:
                result = await self._rpc_call(
                    'OFP.LISTEN',
                    endpoint=endpt,
                    versions=ofversion,
                    tls_id=tls_id,
                    options=options)
                LOGGER.info('Listening on %s [conn_id=%d, versions=%s]', endpt,
                            result.conn_id, ofversion)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to listen on %s: %s', endpt, ex.message)
            raise

    async def _connect_to_endpoints(self):
        """
        Connect to a list of endpoints.
        """
        tls_id = self._config.tls_id
        ofversion = self._config.ofversion
        options = self._config.connect_options
        try:
            for endpt in self._config.connect:
                result = await self._rpc_call(
                    'OFP.CONNECT',
                    endpoint=endpt,
                    versions=ofversion,
                    tls_id=tls_id,
                    options=options)
                LOGGER.info('Connected to %s [conn_id=%d]', endpt,
                            result.conn_id)

        except _exc.ControllerException as ex:
            LOGGER.error('Unable to connect to %s: %s', endpt, ex.message)
            raise

    def _post_event(self, event):
        """
        Post an event to our event queue.
        """
        assert isinstance(event, ObjectView)
        self._event_queue.put_nowait(event)

    def _dispatch_event(self, event):
        """
        Dispatch an event we receive from libofp.
        """
        LOGGER.debug('_dispatch_event %s', event)

        try:
            if 'event' in event:
                self._handle_internal_event(event)
            elif 'id' in event:
                self._handle_rpc_reply(event)
            elif event.method == 'OFP.MESSAGE':
                self._handle_message(event.params)
            elif event.method == 'OFP.CHANNEL':
                self._handle_channel(event.params)
            elif event.method == 'OFP.ALERT':
                self._handle_alert(event.params)
            else:
                LOGGER.warning('Unhandled event: %s', event)
        except _exc.BreakException:
            LOGGER.debug('_dispatch_event: BreakException caught')

    def _write(self, event, xid=None):
        """
        Write an event to the output stream. If `xid` is specified, return a
        `_ReplyFuture` to await the response. Otherwise, return None.
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

    def _rpc_call(self, method, **params):
        """
        Send a RPC request and return a future for the reply.
        """

        xid = self._next_xid()
        event = dict(id=xid, method=method, params=params)
        return self._write(event, xid)

    def _handle_xid(self, event, xid, except_class=None):
        """
        Lookup future associated with given xid and give it the event.
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
        """
        Called when an internal event is received.
        """
        if event['event'] == 'EXIT':
            raise _exc.ExitException()
        for app in self._apps:
            app.event(event)

    def _handle_rpc_reply(self, event):
        """
        Called when a RPC reply is received.
        """
        if 'result' in event:
            result = event.result
            except_class = None
        else:
            result = event
            except_class = _exc.RPCErrorException
        if not self._handle_xid(result, event.id, except_class):
            LOGGER.warning('Unrecognized id in RPC reply: %s', event)

    def _handle_message(self, params):
        """
        Called when a `OFP.MESSAGE` is received.
        """
        if params.type == 'ERROR':
            except_class = _exc.OFPErrorException
        else:
            except_class = None

        if not self._handle_xid(params, params.xid, except_class):
            for app in self._apps:
                app.message(params)

    def _handle_channel(self, params):
        """
        Called when a `OFP.CHANNEL` is received.
        """

        dpid = params.datapath_id if 'datapath_id' in params else None
        scope_key = dpid if dpid else str(params.conn_id)
        LOGGER.info('Datapath %s %s [conn_id=%s, version=%s]', scope_key,
                    params.status, params.conn_id, params.version)
        if params.status == 'DOWN':
            if dpid: self._remove_datapath(dpid)
            self._cancel_tasks(scope_key)
        else:
            if dpid: self._add_datapath(dpid)
        for app in self._apps:
            app.channel(params)

    def _handle_alert(self, params):
        """
        Called when `OFP.ALERT` is received.
        """

        if params.xid and not self._handle_xid(params, params.xid,
                                               _exc.OFPDeliveryException):
            data = params.data.hex()
            if len(data) > 100:
                data = '%s...' % data[:100]
            LOGGER.warning(
                'Alert: %s data=%s (%d bytes) [conn_id=%s, datapath_id=%s, xid=%d]',
                params.alert, data,
                len(params.data), params.conn_id, params.datapath_id,
                params.xid)

    def _idle(self):
        """
        Called once a second to check for timeout expirations.
        """

        now = _timestamp()
        timed_out = [(xid, fut)
                     for (xid, (fut, expiration)) in self._reqs.items()
                     if expiration <= now]
        for xid, fut in timed_out:
            fut.set_exception(_exc.TimeoutException(xid))
            del self._reqs[xid]

        self._idle_task = asyncio.get_event_loop().call_later(_IDLE_INTERVAL,
                                                              self._idle)

    def _set_phase(self, phase):
        """
        Called as the run loop changes phase:
            '' -> PRESTART -> START -> STOP -> POSTSTOP.
        """
        LOGGER.debug('Change phase from "%s" to "%s"', self._phase, phase)
        self._cancel_tasks(self._phase)
        self._phase = phase

    def _next_xid(self):
        """
        Return next xid to use. The controller reserves xid 0 and low numbered
        xid's.
        """

        if self._xid == _MAX_XID:
            self._xid = _MIN_XID
            return self._xid

        self._xid += 1
        return self._xid

    def _ensure_future(self, coroutine, *, scope_key=None, logger=LOGGER):
        """
        Run an async coroutine, within the scope of a specific scope_key.

        This function automatically captures exceptions from the coroutine. It
        also cleans up after the task when it is done.
        """

        async def capture_exception(coroutine):
            try:
                logger.debug('ensure_future: %s', _coro_name(coroutine))
                await coroutine
                logger.debug('ensure_future done: %s', _coro_name(coroutine))
            except asyncio.CancelledError:
                logger.debug('ensure_future cancelled: %s',
                             _coro_name(coroutine))
            except Exception as ex:  # pylint: disable=broad-except
                logger.exception(ex)

        task = asyncio.ensure_future(capture_exception(coroutine))
        if not scope_key:
            scope_key = self._phase
        self._tasks[scope_key].append(task)
        task.add_done_callback(
            functools.partial(
                self._task_callback, scope_key=scope_key))
        return task

    def _cancel_tasks(self, scope_key):
        """
        Cancel async tasks associated with the given scope.

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
        """
        Called when a task is done.
        """
        LOGGER.debug('_task_callback: %s', task)
        self._tasks[scope_key].remove(task)

    def _add_datapath(self, dpid):
        """
        Add a datapath to the controller.
        """
        if dpid in self._datapaths:
            LOGGER.warning('_add_datapath: Datapath %s exists', dpid)
        else:
            self._datapaths.add(dpid)

    def _remove_datapath(self, dpid):
        """
        Remove a datapath from the controller.
        """
        try:
            self._datapaths.remove(dpid)
        except KeyError:
            LOGGER.warning('_remove_datapath: Datapath %s missing', dpid)

    def __repr__(self):
        """
        Return human-readable description of the controller configuration.
        """
        return '\n'.join([repr(app) for app in self._apps])


def _timestamp():
    """
    Return a monotonic timestamp in seconds.
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
