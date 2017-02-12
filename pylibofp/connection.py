"""Implements Connection class."""

import asyncio
import logging
import shutil

_DEFAULT_LIMIT = 2**20  # max line length is 1MB

LOGGER = logging.getLogger('pylibofp.controller')


class Connection(object):
    """Concrete class representing a connection to the `oftr` driver.

    Keyword Args:
        oftr_cmd (str): Subcommand name (defaults to 'jsonrpc')
        oftr_args (Optional[List[str]]): Command line arguments.
    """

    def __init__(self, *, oftr_cmd='jsonrpc', oftr_args=None):
        self._conn = None
        self._input = None
        self._output = None
        self._oftr_cmd = oftr_cmd
        self._oftr_args = oftr_args

    async def connect(self):
        """Set up connection to the oftr driver.
        """
        oftr_path = shutil.which('oftr')
        if not oftr_path:
            raise RuntimeError('Unable to find oftr executable.')

        cmd = [oftr_path, self._oftr_cmd]
        if self._oftr_args:
            cmd.extend(self._oftr_args)

        LOGGER.debug("Launch oftr (%s)", cmd[0])

        try:
            # When we create the subprocess, make it a session leader.
            # We do not want SIGINT signals sent from the terminal to reach
            # the subprocess.
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=_DEFAULT_LIMIT,
                start_new_session=True)
            self._conn = proc
            self._input = proc.stdout
            self._output = proc.stdin

        except (PermissionError, FileNotFoundError):
            LOGGER.error('Unable to find exectuable: "%s"', oftr_path)
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
