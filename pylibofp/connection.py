import asyncio
import logging
import shutil

_DEFAULT_LIMIT = 2**20  # max line length is 1MB

LOGGER = logging.getLogger('pylibofp.controller')


class Connection(object):
    """
    Concrete class representing a connection to the libofp driver.
    """

    def __init__(self, *, libofp_args=None):
        """
        Initialize connection.
        """
        self._conn = None
        self._input = None
        self._output = None
        self._libofp_args = libofp_args

    async def connect(self):
        """
        Set up connection to the libofp driver.
        """

        libofp_path = shutil.which('libofp')
        if not libofp_path:
            raise RuntimeError('Unable to find libofp executable.')

        cmd = [libofp_path, 'jsonrpc']
        if self._libofp_args:
            cmd.extend(self._libofp_args)

        LOGGER.debug("Launch libofp (%s)", cmd[0])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=_DEFAULT_LIMIT)
            self._conn = proc
            self._input = proc.stdout
            self._output = proc.stdin

        except (PermissionError, FileNotFoundError):
            LOGGER.error('Unable to find exectuable: "%s"', libofp_path)
            raise


    async def disconnect(self):
        """
        Wait for libofp connection to close.
        """
        return_code = await self._conn.wait()
        LOGGER.info("libofp exited with return code %s", return_code)
        self._input = None
        self._output = None
        self._conn = None

    async def readline(self):
        """
        Return next incoming line from the connection.
        """
        return await self._input.readline()

    def write(self, data):
        """
        Write data to the connection.
        """
        self._output.write(data)

    async def drain(self):
        """
        Wait while the output buffer is flushed.
        """
        LOGGER.info('libofp connection drain: buffer_size=%d', self.get_write_buffer_size())
        return await self._output.drain()

    def close(self):
        """
        Close the connection.
        """
        try:
            self._conn.terminate()
        except ProcessLookupError:
            # Ignore failure when process already died.
            pass

    def get_write_buffer_size(self):
        """
        Return size of the write buffer.
        """
        return self._output.transport.get_write_buffer_size()
