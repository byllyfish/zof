"""Implements Connection class."""

import asyncio
import logging
import shutil
import shlex
from zof.protocol import Protocol

_DEFAULT_LIMIT = 2**20  # max line length is 1MB

LOGGER = logging.getLogger(__package__)


class Connection(object):
    """Concrete class representing a connection to the `oftr` driver.

    This class supports both the stream and protocol API's. If you pass a
    'post_message' function argument to `connect()`, you will use the protocol
    API which may be faster.

    Keyword Args:
        oftr_options (Dict[str, str]): Dictionary with options:
                path: Path to oftr executable (default=<local system path>)
                subcmd: Subcommand name (default='jsonrpc')
                args: Command line arguments for oftr (default='')
                prefix: Command line prefix for launching oftr (default='')

    The command to execute oftr are constructed from oftr_options:

        "<prefix> <path> <subcmd> <args>"
    """

    def __init__(self, *, oftr_options=None):
        if oftr_options is None:
            oftr_options = {}
        # Verify that connection options are all strings or None.
        for key, value in oftr_options.items():
            if value is not None and not isinstance(value, str):
                raise ValueError('Unexpected oftr option: %s=%r' % (key,
                                                                    value))
        self._conn = None
        self._input = None
        self._output = None
        self._protocol = None
        self._pid = None

        oftr_path = self.find_oftr_path(oftr_options.get('path'))
        oftr_subcmd = oftr_options.get('subcmd') or 'jsonrpc'
        oftr_args = oftr_options.get('args') or ''
        oftr_prefix = oftr_options.get('prefix') or ''

        # Construct the cmd used to launch oftr subprocess.
        cmd = '%s %s %s %s' % (oftr_prefix, oftr_path, oftr_subcmd, oftr_args)
        self._oftr_cmd = shlex.split(cmd)
        assert self._oftr_cmd

    @property
    def pid(self):
        """Return process ID for oftr process.

        Returns:
            (int) process id of oftr process (or None if not running)
        """
        return self._pid

    async def connect(self, post_message=None):
        """Set up connection to the oftr driver.

        If the 'post_message' argument is present, use the faster protocol api.

        Args:
            post_message (function): single arg function to post received
                message events
        Returns:
            (int) process id of oftr process
        """
        # If a callback is provided, use the asyncio protocol api.
        if post_message:
            return await self._connect_protocol(post_message)

        LOGGER.debug("Launch oftr %r (stream API)", self._oftr_cmd)

        try:
            # When we create the subprocess, make it a session leader.
            # We do not want SIGINT signals sent from the terminal to reach
            # the subprocess.
            proc = await asyncio.create_subprocess_exec(
                *self._oftr_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=_DEFAULT_LIMIT,
                start_new_session=True)
            self._conn = proc
            self._input = proc.stdout
            self._output = proc.stdin
            self._pid = proc.pid
            return self._pid

        except (PermissionError, FileNotFoundError):
            LOGGER.error('Unable to find executable: "%r"', self._oftr_cmd)
            raise

    async def _connect_protocol(self, post_message):
        """Set up connection to oftr driver (using the Protocol api).

        Returns:
            (int) process id of oftr process
        """
        LOGGER.debug("Launch oftr %r (protocol API)", self._oftr_cmd)

        try:
            # When we create the subprocess, make it a session leader.
            # We do not want SIGINT signals sent from the terminal to reach
            # the subprocess.
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.subprocess_exec(
                lambda: Protocol(post_message),
                *self._oftr_cmd,
                stderr=None,
                start_new_session=True)
            self._conn = transport
            self._protocol = protocol
            self._input = transport.get_pipe_transport(1)
            self._output = transport.get_pipe_transport(0)
            self._pid = transport.get_pid()
            return self._pid

        except (PermissionError, FileNotFoundError):
            LOGGER.error('Unable to find executable: "%r"', self._oftr_cmd)
            raise

    async def disconnect(self):
        """Wait for oftr connection to close.
        """
        if self._conn is None:
            return 0
        if self._protocol:
            await self._protocol.exit_future
            self._conn.close()
            return_code = self._conn.get_returncode()
        else:
            return_code = await self._conn.wait()
        if return_code:
            LOGGER.error("oftr exited with return code %s", return_code)
        self._input = None
        self._output = None
        self._conn = None
        self._protocol = None
        self._pid = None
        return return_code

    async def readline(self, delimiter=b'\x00'):
        """Read next incoming line from the connection.
        """
        try:
            result = await self._input.readuntil(delimiter)
            return result[0:-1]
        except asyncio.streams.IncompleteReadError as ex:
            if ex.partial:
                LOGGER.warning('oftr incomplete read: %d bytes ignored',
                               len(ex.partial))
            return b''

    def write(self, data, delimiter=b'\x00'):
        """Write data to the connection.
        """
        self._output.write(data + delimiter if delimiter else data)

    async def drain(self):
        """Wait while the output buffer is flushed.
        """
        LOGGER.info('oftr connection drain: buffer_size=%d',
                    self.get_write_buffer_size())
        return await self._output.drain()

    def close(self, write=False):
        """Close the connection.
        """
        if self._conn is None:
            return
        if write:
            self._output.close()
        else:
            try:
                self._conn.terminate()
            except ProcessLookupError:
                # Ignore failure when process already died.
                pass

    def is_closed(self):
        """Return true if connection is closed.
        """
        return self._output is None

    def get_write_buffer_size(self):
        """Get size of the write buffer.
        """
        return self._output.transport.get_write_buffer_size()

    @staticmethod
    def find_oftr_path(default=None):
        """Return path to oftr executable.
        """
        if default:
            return default
        path = shutil.which('oftr')
        if not path:
            raise RuntimeError('Unable to find oftr executable.')
        return path
