"""Protocol class for oftr driver."""

import asyncio
import json
from ipaddress import IPv4Address, IPv6Address

from zof.exception import RequestError
from zof.log import logger


class OftrProtocol(asyncio.SubprocessProtocol):
    """Protocol subclass that implements communication with OFTR."""

    def __init__(self, dispatch, loop):
        """Initialize protocol."""
        self.dispatch = dispatch
        self._loop = loop
        self._recv_buf = bytearray()
        self._transport = None
        self._write = None
        self._request_futures = {}
        self._closed_future = None
        self._idle_handle = None

    def send(self, msg):
        """Send an OpenFlow/RPC message."""
        assert self._write

        data = zof_dump_msg(msg)
        self._write(data)

    def request(self, msg):
        """Send an OpenFlow/RPC message and wait for a reply."""
        assert self._write

        xid = msg.get('id')
        if xid is None:
            xid = msg['params']['xid']

        data = zof_dump_msg(msg)
        self._write(data)

        req_info = _RequestInfo(self._loop, 3.0)
        self._request_futures[xid] = req_info
        return req_info.future

    def pipe_data_received(self, fd, data):
        """Read data from pipe into buffer and dispatch incoming messages."""
        buf = self._recv_buf
        offset = len(buf)
        buf += data
        begin = 0

        while True:
            # Search for end-of-message byte.
            offset = buf.find(b'\x00', offset)

            # If not found, reset buffer and return.
            if offset < 0:
                if begin > 0:
                    del buf[0:begin]  # pytype: disable=wrong-arg-types
                return

            # If message is non-empty, parse it and dispatch it.
            assert buf[offset] == 0
            if begin != offset:
                msg = zof_load_msg(buf[begin:offset])
                if msg:
                    self.handle_msg(msg)

            # Move on to next message in buffer (if present).
            offset += 1
            begin = offset

    def handle_msg(self, msg):
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
            logger.error('Driver.handle_msg: Ignored msg: %r', msg)

    def connection_made(self, transport):
        """Handle new incoming connection."""
        self._transport = transport
        self._write = transport.get_pipe_transport(0).write
        self._closed_future = self._loop.create_future()
        self._idle_handle = self._loop.call_later(0.5, self._idle)

    def connection_lost(self, exc):
        """Handle disconnect."""
        self._cancel_requests()
        self._closed_future.set_result(1)
        self._idle_handle.cancel()
        self._write = None
        self._transport = None

    def _idle(self):
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

    async def stop(self):
        """Stop the OpenFlow driver."""
        if self._transport:
            # N.B. Do not call close(); it's unreliable under uvloop.
            self._transport.terminate()

            # Wait for connection_lost to be called.
            await self._closed_future


class _RequestInfo:
    """Manage information about in-flight requests."""

    def __init__(self, loop, timeout):
        self.future = loop.create_future()
        self.expiration = loop.time() + timeout

    def handle_reply(self, msg):
        """Handle event that replies to a request."""
        if 'type' in msg:
            if msg['type'] in ('ERROR', 'CHANNEL_ALERT'):
                self.future.set_exception(RequestError(msg))
            else:
                self.future.set_result(msg)
        elif 'result' in msg:
            self.future.set_result(msg['result'])
        elif 'error' in msg:
            self.future.set_exception(RequestError(msg))
        else:
            logger.error('OFTR: Unexpected reply: %r', msg)

    def handle_timeout(self, xid):
        """Handle timeout of a request."""
        self.future.set_exception(RequestError.zof_timeout(xid))

    def handle_closed(self, xid):
        """Handle connection close while request in flight."""
        self.future.set_exception(RequestError.zof_closed(xid))


def zof_load_msg(data):
    """Read from JSON bytes."""
    try:
        return json.loads(data)
    except Exception:  # pylint: disable=broad-except
        logger.exception('zof_load_msg exception: %r', data)
    return None


def zof_dump_msg(msg):
    """Write to JSON bytes (with delimiter)."""
    return json.dumps(
        msg,
        ensure_ascii=False,
        allow_nan=False,
        check_circular=False,
        default=zof_json_serialize).encode('utf-8') + b'\0'


def zof_json_serialize(obj):
    """Support JSON serialization for common object types."""
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, (IPv4Address, IPv6Address)):
        return str(obj)
    raise TypeError('Value "%s" of type %s is not JSON serializable' %
                    (repr(obj), type(obj)))
