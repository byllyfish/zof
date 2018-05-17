"""Implements a Driver class for communicating with `oftr`."""

import asyncio
import shutil
import shlex
import logging

from zoflite.protocol import OftrProtocol, RequestError

LOGGER = logging.getLogger(__package__)


def _noop(driver, event):  # pragma: no cover
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

    def __init__(self, dispatch=_noop, debug=False):
        """Initialize event callback."""

        self.dispatch = dispatch
        self.pid = None
        self._debug = debug
        self._protocol = None
        self._last_xid = 0

    async def __aenter__(self):
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

        self._protocol = protocol
        self.pid = transport.get_pid()

        return self

    async def __aexit__(self, *_args):
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

    async def listen(self, endpoint, options=(), versions=()) -> int:
        """Listen for OpenFlow connections on a given endpoint."""

        request = self._ofp_listen(endpoint, options, versions)
        reply = await self.request(request)
        return reply['conn_id']

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

    def _oftr_cmd(self):
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
