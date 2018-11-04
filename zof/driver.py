"""Implements a Driver class for communicating with `oftr`."""

import asyncio
import shutil
import shlex

from zof.log import logger
from zof.oftr import OftrProtocol

# XID values 0-255 are reserved. XID values are only assigned
# values between 256 and 2**32-255.
_MAX_RESERVED_XID = 0xff
_MAX_DYNAMIC_XID = 0xffffff00


class Driver:
    """Concrete class that communicates with oftr.

    The driver implements the basic OpenFlow RPC commands: listen, connect,
    send and request. It facilitates request/reply pairing and dispatches
    incoming events to higher layers.

    A driver normally uses `async with`:

        async with Driver() as driver:
            conn_id = await driver.connect('127.0.0.1:6653')
            ...
            await driver.close(conn_id)

    Attributes:
        event_queue (Queue): Queue of incoming events.
        pid (int): Process ID of oftr tool.

    """

    def __init__(self, *, debug=False):
        """Initialize event callback."""
        self.event_queue = None
        self.pid = None
        self._debug = debug
        self._protocol = None
        self._xid = _MAX_RESERVED_XID

    async def __aenter__(self):
        """Async context manager entry point."""
        assert not self._protocol, 'Driver already open'

        cmd = self._oftr_cmd()
        loop = asyncio.get_running_loop()
        self.event_queue = asyncio.Queue()

        def _proto_factory():
            return OftrProtocol(self.post_event, loop)

        # When we create the subprocess, make it a session leader.
        # We do not want SIGINT signals sent from the terminal to reach
        # the subprocess.
        transport, protocol = await loop.subprocess_exec(
            _proto_factory, *cmd, stderr=None, start_new_session=True)

        self._protocol = protocol
        self.pid = transport.get_pid()

        return self

    async def __aexit__(self, *_args):
        """Async context manager exit point."""
        assert self._protocol, 'Driver not open'

        qsize = self.event_queue.qsize()
        if qsize > 0:
            logger.warning('Exiting with %d events in queue', qsize)

        # Tell the subprocess to stop, then wait for it to exit.
        await self._protocol.stop()

        self._protocol = None
        self.pid = None

    def send(self, event):
        """Send a RPC or OpenFlow message."""
        assert self._protocol, 'Driver not open'

        if 'method' not in event:
            event = self._ofp_send(event)
        self._protocol.send(event)

    async def request(self, event):
        """Send a RPC or OpenFlow message and wait for a reply."""
        assert self._protocol, 'Driver not open'

        if 'method' not in event:
            event = self._ofp_send(event)
        return await self._protocol.request(event)

    async def listen(self, endpoint, options=(), versions=(), tls_id=0):
        """Listen for OpenFlow connections on a given endpoint."""
        request = self._ofp_listen(endpoint, options, versions, tls_id)
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

    def close_nowait(self, conn_id):
        """Close an OpenFlow connection."""
        request = self._ofp_close_nowait(conn_id)
        self.send(request)

    async def add_identity(self, cert, cacert, privkey):
        """Add TLS identity."""
        request = self._ofp_add_identity(cert, cacert, privkey)
        reply = await self.request(request)
        return reply['tls_id']

    def post_event(self, event):
        """Dispatch event."""
        assert 'type' in event, repr(event)
        self.event_queue.put_nowait(event)

    def _oftr_cmd(self):
        """Return oftr command with args."""
        cmd = '%s jsonrpc'
        if self._debug:
            cmd += ' --trace=rpc'
        return shlex.split(cmd % shutil.which('oftr'))

    def _assign_xid(self):
        """Return the next xid to use for a request/send."""
        self._xid += 1
        if self._xid > _MAX_DYNAMIC_XID:
            self._xid = _MAX_RESERVED_XID + 1
        return self._xid

    def _ofp_send(self, event):
        if 'type' not in event:
            raise ValueError('Invalid event (missing type): %r' % event)
        if 'xid' not in event:
            event['xid'] = self._assign_xid()
        elif event['xid'] > _MAX_RESERVED_XID:
            raise ValueError('Invalid event (invalid xid): %r' % event)
        return {'method': 'OFP.SEND', 'params': event}

    def _ofp_listen(self, endpoint, options, versions, tls_id):
        return {
            'id': self._assign_xid(),
            'method': 'OFP.LISTEN',
            'params': {
                'endpoint': endpoint,
                'options': options,
                'versions': versions,
                'tls_id': tls_id
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

    @staticmethod
    def _ofp_close_nowait(conn_id):
        return {'method': 'OFP.CLOSE', 'params': {'conn_id': conn_id}}

    def _ofp_add_identity(self, cert, cacert, privkey):
        return {
            'id': self._assign_xid(),
            'method': 'OFP.ADD_IDENTITY',
            'params': {
                'cert': cert,
                'cacert': cacert,
                'privkey': privkey
            }
        }
