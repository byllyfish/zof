"""Protocol class for oftr driver."""

import asyncio
import shutil
import shlex

from zof.exception import RequestError
from zof.log import logger
from zof.util import from_json, to_json


class OftrProtocol(asyncio.Protocol):
    """Protocol subclass that implements communication with OFTR."""

    def __init__(self, dispatch, loop):
        """Initialize protocol."""
        self.dispatch = dispatch
        self.process = None
        self._loop = loop
        self._recv_buf = bytearray()
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

    def data_received(self, data):
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
                    del buf[0:begin]
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

        req_info = self._request_futures.get(xid)
        if req_info and _valid_reply(ofp_msg, msg):
            if req_info.handle_reply(msg):
                del self._request_futures[xid]
        elif ofp_msg:
            self.dispatch(msg)
        else:
            logger.error('Driver.handle_msg: Ignored msg: %r', msg)

    def connection_made(self, transport):
        """Handle new incoming connection."""
        self._write = transport.write
        self._closed_future = self._loop.create_future()
        self._idle_handle = self._loop.call_later(0.5, self._idle)

    def connection_lost(self, exc):
        """Handle disconnect."""
        self._cancel_requests()
        self._closed_future.set_result(1)
        self._idle_handle.cancel()
        self._write = None

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

    @classmethod
    async def start(cls, post_event, debug):
        """Connect to the the OpenFlow driver process."""
        cmd, socket_path = OftrProtocol._oftr_cmd(debug)
        loop = asyncio.get_running_loop()

        # When we create the subprocess, make it a session leader.
        # We do not want SIGINT signals sent from the terminal to reach
        # the subprocess.

        proc = await asyncio.create_subprocess_exec(
            *cmd, loop=loop, stdin=None, stdout=None, stderr=None, start_new_session=True)
        await asyncio.sleep(0.1)

        def _proto_factory():
            return cls(post_event, loop)

        _, protocol = await loop.create_unix_connection(_proto_factory, socket_path)
        protocol.process = proc

        return protocol

    async def stop(self):
        """Stop the OpenFlow driver."""
        if self.process:
            # Tell the subprocess to stop, then wait for it to exit.
            try:
                self.process.terminate()
            except ProcessLookupError:
                pass

            # Wait for connection_lost to be called.
            await self._closed_future
            self.process = None

    @staticmethod
    def _oftr_cmd(debug):
        """Return oftr command with args."""
        socket_path = 'oftr.ipc'
        cmd = '%s jsonrpc'
        if debug:
            cmd += ' --trace=rpc'
        if socket_path:
            cmd += ' --rpc-socket=%s' % socket_path
        result = shlex.split(cmd % shutil.which('oftr'))
        return result, socket_path


class _RequestInfo:
    """Manage information about in-flight requests."""

    def __init__(self, loop, timeout):
        self.future = loop.create_future()
        self.expiration = loop.time() + timeout
        self.multipart_reply = None

    def handle_reply(self, msg):
        """Handle event that replies to a request.

        Returns:
            bool: True if reply was fully received.

        """
        if self.future.done():
            return False
        result = True
        if 'type' in msg:
            flags = msg.get('flags')
            if msg['type'] in ('ERROR', 'CHANNEL_ALERT'):
                self.future.set_exception(RequestError(msg))
            elif flags and 'MORE' in flags:
                self.handle_multipart_middle(msg)
                result = False
            elif self.multipart_reply is not None:
                self.handle_multipart_last(msg)
            else:
                self.future.set_result(msg)
        elif 'result' in msg:
            self.future.set_result(msg['result'])
        elif 'error' in msg:
            self.future.set_exception(RequestError(msg))
        else:
            logger.error('OFTR: Unexpected reply: %r', msg)
        return result

    def handle_timeout(self, xid):
        """Handle timeout of a request."""
        if not self.future.done():
            self.future.set_exception(RequestError.zof_timeout(xid))

    def handle_closed(self, xid):
        """Handle connection close while request in flight."""
        if not self.future.done():
            self.future.set_exception(RequestError.zof_closed(xid))

    def handle_multipart_middle(self, msg):
        """Handle multipart message with the more flag."""
        if self.multipart_reply is None:
            self.multipart_reply = msg
        else:
            self._append_multipart(msg)

    def handle_multipart_last(self, msg):
        """Handle last multipart message."""
        self._append_multipart(msg)
        self.future.set_result(self.multipart_reply)

    def _append_multipart(self, msg):
        if msg['type'] != self.multipart_reply['type']:
            logger.warning('Inconsistent multipart type: %s (expected %s)',
                           msg['type'], self.multipart_reply['type'])
            return
        assert isinstance(self.multipart_reply['msg'], list)
        assert isinstance(msg['msg'], list)
        self.multipart_reply['msg'].extend(msg['msg'])


def _valid_reply(ofp_msg, msg):
    """Return true if `msg` is not an async OpenFlow message.

    Args:
        ofp_msg (bool): True if msg is OpenFlow message (instead of RPC).
        msg (dict): OpenFlow message
    """
    if not ofp_msg:
        return True
    return msg['type'] not in ('PACKET_IN', 'FLOW_REMOVED', 'PORT_STATUS')


def zof_load_msg(data):
    """Read from JSON bytes."""
    try:
        return from_json(data)
    except Exception:  # pylint: disable=broad-except
        logger.exception('zof_load_msg exception: %r', data)
    return None


def zof_dump_msg(msg):
    """Write compact JSON bytes (with delimiter)."""
    return to_json(msg).encode('utf-8') + b'\0'
