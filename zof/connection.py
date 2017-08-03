"""Implements Connection class."""

import asyncio
import logging
import shutil
import shlex

_DEFAULT_LIMIT = 2**20  # max line length is 1MB

LOGGER = logging.getLogger(__package__)


class Connection(object):
    """Concrete class representing a connection to the `oftr` driver.

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
                raise ValueError('Unexpected oftr option: %s=%r' %
                                 (key, value))
        self._conn = None
        self._input = None
        self._output = None

        oftr_path = oftr_options.get('path') or ''
        oftr_subcmd = oftr_options.get('subcmd') or 'jsonrpc'
        oftr_args = oftr_options.get('args') or ''
        oftr_prefix = oftr_options.get('prefix') or ''

        # The default path is to the local executable.
        if not oftr_path:
            oftr_path = shutil.which('oftr')
            if not oftr_path:
                raise RuntimeError('Unable to find oftr executable.')

        # Construct the cmd used to launch oftr subprocess.
        cmd = '%s %s %s %s' % (oftr_prefix, oftr_path, oftr_subcmd, oftr_args)
        self._oftr_cmd = shlex.split(cmd)
        assert self._oftr_cmd

    @property
    def pid(self):
        """Return process ID for oftr process.

        Raises:
            RuntimeError if process is not running.
        """
        try:
            return self._conn.pid
        except:
            raise RuntimeError('oftr process is not running')

    async def connect(self):
        """Set up connection to the oftr driver.

        Returns:
            (int) process id of oftr process
        """
        LOGGER.debug("Launch oftr %r", self._oftr_cmd)

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
            return proc.pid

        except (PermissionError, FileNotFoundError):
            LOGGER.error('Unable to find executable: "%r"', self._oftr_cmd)
            raise

    async def disconnect(self):
        """Wait for oftr connection to close.
        """
        if self._conn is None:
            return 0
        return_code = await self._conn.wait()
        if return_code:
            LOGGER.error("oftr exited with return code %s", return_code)
        self._input = None
        self._output = None
        self._conn = None
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

    def get_write_buffer_size(self):
        """Get size of the write buffer.
        """
        return self._output.transport.get_write_buffer_size()
