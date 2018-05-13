"""Implements a Driver for communicating with `oftr`."""

import asyncio
import shutil
import shlex
import json
import logging

from typing import Any, Callable, Optional, Awaitable, Dict, Union, List, cast

# Declare common types.
#
# TODO(bfish): Use recursive types (https://github.com/python/mypy/issues/731)
#    JSON = Union[Dict[str, 'JSON'], List['JSON'], str, int, float, bool, None]
Event = Dict[str, Any]
EventCallback = Callable[['Driver', Event], None]
"""
TODO:
    No task context for current conn_id/datapath_id. Use event['datapath'] object.
    Support for 'other' handler in Dispatcher.
    Fix support for event delimiter.
    Add support for default ofp.listen.
    Datapath class.
    Wrap callbacks so exceptions are reported.
    Add timeout checking periodic timer.

    Test: send() and request() should not modify the dict object.
    Test: send() and request() should auto-fill the conn_id and xid.
    
    Async dispatch will still be supported. There will be simple code to deal with async
    start and tracking datapath-dependent tasks.

    zof.send and zof.request need to use conn_id to set?
    No support for signals. Use asyncio callback instead.

    
"""

LOGGER = logging.getLogger(__package__)


class RequestError(Exception):
    """Represents a failure of the request() api.

    Attributes:
        message (str): human-readable error message
    """

    def __init__(self, event):
        assert event.get('error') is not None or event.get('type') == 'ERROR'
        super().__init__(event)
        self.message = event['error']['message']


def _noop(driver, event) -> None:
    pass


class Driver:
    """Concrete class that manages communication with the `oftr` OpenFlow library. 

    The driver implements the basic OpenFlow RPC commands: listen, connect, send 
    and request. It facilitates request/reply pairing and dispatches incoming 
    events to higher layers.
    
    The driver is initialized with a `dispatcher` parameter. The dispatcher is
    a 2-arg callable used to dispatch incoming events. The dispatcher arguments are
    (driver, event).

    Example (no dispatcher):

        ofmsg = {'type': 'REQUEST.DESC'}

        async with zof.Driver() as driver:
            conn_id = await driver.connect('127.0.0.1:6653')
            reply = await driver.request(ofmsg, conn_id=conn_id)
            print(reply)

    Example (with a dispatcher):

        def dispatcher(driver, event):
            print(event)

        async with zof.Driver(dispatcher) as driver:
            await driver.listen(':6653')
            await asyncio.sleep(30)
    """

    def __init__(self, dispatch: EventCallback = _noop, debug=False) -> None:
        """Initialize event callback."""

        self.dispatch = dispatch  # type: EventCallback
        self._debug = debug
        self._protocol = None  # type: Optional[OftrProtocol]
        self._last_xid = 0  # type: int
        self.pid = None  # type: Optional[int]

    async def __aenter__(self) -> 'Driver':
        """Async context manager entry point."""

        assert not self._protocol, 'Driver already open'

        cmd = self._oftr_cmd()
        loop = asyncio.get_event_loop()
        proto_factory = lambda: OftrProtocol(self.post_event, loop)

        # When we create the subprocess, make it a session leader.
        # We do not want SIGINT signals sent from the terminal to reach
        # the subprocess.
        transport, protocol = await loop.subprocess_exec(
            proto_factory, *cmd, stderr=None, start_new_session=True)

        self._protocol = cast(OftrProtocol, protocol)
        self.pid = cast(asyncio.SubprocessTransport, transport).get_pid()

        return self

    async def __aexit__(self, *_args: List[Any]) -> None:
        """Async context manager exit point."""

        assert self._protocol, 'Driver not open'

        # Tell the subprocess to stop, then wait for it to exit.
        await self._protocol.stop()

        self._protocol = None
        self.pid = None

    def send(self, msg):
        """Send an OpenFlow message.

        OpenFlow messages may be modified by having an xid value assigned.
        """

        assert self._protocol, 'Driver not open'

        if 'method' not in msg:
            msg = self._ofp_send(msg)

        self._protocol.send(msg)

    async def request(self, msg):
        """Send an OpenFlow message and wait for a reply."""

        assert self._protocol, 'Driver not open'

        if 'method' not in msg:
            msg = self._ofp_send(msg)

        return await self._protocol.request(msg)

    async def listen(self, endpoint: str, options=(), versions=()) -> int:
        """Listen for OpenFlow connections on a given endpoint."""

        request = self._ofp_listen(endpoint, options, versions)
        reply = await self.request(request)
        return cast(int, reply['conn_id'])

    async def connect(self, endpoint):
        """Make outgoing OpenFlow connection to given endpoint."""

        request = self._ofp_connect(endpoint)
        reply = await self.request(request)
        return reply['conn_id']

    async def close(self, conn_id):
        """Close an OpenFlow connection."""

        request = self._ofp_close(conn_id)
        reply = await self.request(request)
        return reply['count']

    def post_event(self, event):
        """Dispatch event."""

        assert 'type' in event, repr(event)
        self.dispatch(self, event)

    def _oftr_cmd(self) -> List[str]:
        """Return oftr command with args."""

        cmd = '%s jsonrpc'
        if self._debug:
            cmd += ' --trace=rpc'

        return shlex.split(cmd % shutil.which('oftr'))

    def _assign_xid(self):
        """Return the next xid to use for a request/send."""

        self._last_xid += 1
        return self._last_xid

    def _ofp_send(self, msg):
        if 'type' not in msg:
            return msg
        if 'xid' not in msg:
            msg['xid'] = self._assign_xid()
        return {'method': 'OFP.SEND', 'params': msg}

    def _ofp_listen(self, endpoint, options, versions):
        return {
            'id': self._assign_xid(),
            'method': 'OFP.LISTEN',
            'params': {
                'endpoint': endpoint,
                'options': options,
                'versions': versions
            }
        }

    def _ofp_connect(self, endpoint):
        return {
            'id': self._assign_xid(),
            'method': 'OFP.CONNECT',
            'params': {
                'endpoint': endpoint
            }
        }

    def _ofp_close(self, conn_id):
        return {
            'id': self._assign_xid(),
            'method': 'OFP.CLOSE',
            'params': {
                'conn_id': conn_id
            }
        }


class OftrProtocol(asyncio.SubprocessProtocol):
    """Protocol subclass that implements communication with OFTR."""

    def __init__(self, dispatch, loop) -> None:
        """Initialize protocol."""

        self.dispatch = dispatch  # type: EventCallback
        self._loop = loop
        self._recv_buf = bytearray()
        self._transport = None  # type: Optional[asyncio.SubprocessTransport]
        self._write = None  # type: Optional[Callable[[bytes], None]]
        self._request_futures = {}  # type: Dict[int, _RequestInfo]
        self._closed_future = None
        self._idle_handle = None

    def send(self, msg: Event) -> None:
        """Send an OpenFlow/RPC message."""

        assert self._write

        data = _dump_msg(msg)
        self._write(data)

    def request(self, msg: Event) -> Awaitable[Event]:
        """Send an OpenFlow/RPC message and wait for a reply."""

        assert self._write

        xid = msg.get('id')
        if xid is None:
            params = msg.get('params')
            if isinstance(params, dict):
                xid = params['xid']
            else:
                raise ValueError('Missing xid: %r', msg)

        data = _dump_msg(msg)
        self._write(data)

        req_info = _RequestInfo(self._loop, 3.0)
        self._request_futures[xid] = req_info
        return req_info.future

    def pipe_data_received(self, fd: int, data: Union[bytes, str]) -> None:
        """Read data from pipe into buffer and dispatch incoming messages."""

        buf = self._recv_buf
        offset = len(buf)
        buf += data
        begin = 0

        while True:
            # Search for end-of-message byte.
            offset = buf.find(0, offset)

            # If not found, reset buffer and return.
            if offset < 0:
                if begin > 0:
                    del buf[0:begin]
                return

            # If message is non-empty, parse it and dispatch it.
            assert buf[offset] == 0
            if begin != offset:
                msg = _load_msg(buf[begin:offset])
                self.handle_msg(msg)

            # Move on to next message in buffer (if present).
            offset += 1
            begin = offset

    def handle_msg(self, msg: Event) -> None:
        """Handle incoming message."""

        if msg.get('method') == 'OFP.MESSAGE':
            msg = msg['params']
            xid = msg.get('xid')
            ofp_msg = True
        else:
            xid = msg.get('id')
            ofp_msg = False

        req_info = self._request_futures.pop(xid, None)
        if req_info is not None:
            req_info.handle_reply(msg)
        elif ofp_msg:
            self.dispatch(msg)
        else:
            LOGGER.error('Driver.handle_msg: Ignored msg: %r', msg)

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = cast(asyncio.SubprocessTransport, transport)
        write_transport = cast(asyncio.WriteTransport,
                               self._transport.get_pipe_transport(0))
        self._write = write_transport.write
        self._closed_future = self._loop.create_future()
        self._idle_handle = self._loop.call_later(0.5, self._idle)

    def connection_lost(self, exc: Exception) -> None:
        self._cancel_requests()
        self._closed_future.set_result(1)
        self._idle_handle.cancel()
        self._write = None
        self._transport = None

    def _idle(self) -> None:
        """Idle task handler."""

        expired = [(xid, info)
                   for (xid, info) in self._request_futures.items()
                   if info.expiration <= self._loop.time()]
        for xid, info in expired:
            info.handle_timeout(xid)
            del self._request_futures[xid]
        self._idle_handle = self._loop.call_later(0.5, self._idle)

    def _cancel_requests(self):
        """Cancel all pending requests."""

        for xid, info in self._request_futures.items():
            info.handle_closed(xid)
        self._request_futures = {}

    async def stop(self) -> None:
        """Stop the OpenFlow driver."""

        if self._transport:
            # N.B. Do not call close(); it's unreliable under uvloop.
            self._transport.terminate()

            # Wait for connection_lost to be called.
            await self._closed_future


class _RequestInfo:
    def __init__(self, loop, timeout: float) -> None:
        self.future = loop.create_future()  # type: asyncio.Future[Event]
        self.expiration = loop.time() + timeout  # type: float

    def handle_reply(self, msg: Event) -> None:
        if 'type' in msg:
            if msg['type'] == 'ERROR':
                self.future.set_exception(RequestError(msg))
            else:
                self.future.set_result(msg)
        elif 'result' in msg:
            self.future.set_result(msg['result'])
        elif 'error' in msg:
            self.future.set_exception(RequestError(msg))
        else:
            LOGGER.error('OFTR: Unexpected reply: %r', msg)

    def handle_timeout(self, xid) -> None:
        # Synthesize an error reply to stand in for the timeout error.
        msg = {'id': xid, 'error': {'message': 'request timeout'}}
        self.future.set_exception(RequestError(msg))

    def handle_closed(self, xid) -> None:
        # Synthesize an error reply to stand in for close error.
        msg = {'id': xid, 'error': {'message': 'connection closed'}}
        self.future.set_exception(RequestError(msg))


def _load_msg(data: Union[bytes, str]) -> Event:
    try:
        msg = json.loads(data)
        return cast(Event, msg)
    except Exception as ex:
        return {'type': 'DRIVER_ALERT', 'msg': data}


def _dump_msg(msg: Event) -> bytes:
    return json.dumps(
        msg, ensure_ascii=False, allow_nan=False,
        check_circular=False).encode('utf-8') + b'\0'


def main() -> None:
    async def _test() -> None:
        async with Driver() as driver:
            from timeit import default_timer as timer

            DESC = {'method': 'OFP.DESCRIPTION'}
            start_time = timer()
            for _ in range(10000):
                result = await driver.request(DESC)
                #print(result)
            print(driver.pid, timer() - start_time)

            try:
                conn_id = await driver.listen('6653')
                print(driver.pid, 'conn_id=%d' % conn_id)
            except RequestError as ex:
                print(driver.pid, 'error: %s' % ex)
            await asyncio.sleep(60)

    #import uvloop
    #asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    for _ in range(1):
        asyncio.ensure_future(_test())
    asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    main()
