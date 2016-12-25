"""Implements Connection class."""

import asyncio
import logging
import shutil
import os

_DEFAULT_LIMIT = 2**20  # max line length is 1MB

LOGGER = logging.getLogger('pylibofp.controller')


class Connection(object):
    """Concrete class representing a connection to the libofp driver.

    Keyword Args:
        libofp_cmd (str): Subcommand name (defaults to 'jsonrpc')
        libofp_args (Optional[List[str]]): Command line arguments.
    """

    def __init__(self, *, libofp_cmd='jsonrpc', libofp_args=None):
        self._conn = None
        self._input = None
        self._output = None
        self._libofp_cmd = libofp_cmd
        self._libofp_args = libofp_args

    async def connect(self):
        """Set up connection to the libofp driver.
        """
        libofp_path = shutil.which('libofp')
        if not libofp_path:
            raise RuntimeError('Unable to find libofp executable.')

        cmd = [libofp_path, self._libofp_cmd]
        if self._libofp_args:
            cmd.extend(self._libofp_args)

        LOGGER.debug("Launch libofp (%s)", cmd[0])

        try:
            # When we create the subprocess, we force it into its own process
            # group using the `prexec_fn` argument. We do not want SIGINT 
            # signals sent from the terminal to reach the subprocess.
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                limit=_DEFAULT_LIMIT,
                preexec_fn=os.setpgrp)
            self._conn = proc
            self._input = proc.stdout
            self._output = proc.stdin

        except (PermissionError, FileNotFoundError):
            LOGGER.error('Unable to find exectuable: "%s"', libofp_path)
            raise

    async def disconnect(self):
        """Wait for libofp connection to close.
        """
        if self._conn is None:
            return 0
        return_code = await self._conn.wait()
        if return_code:
            LOGGER.error("libofp exited with return code %s", return_code)
        self._input = None
        self._output = None
        self._conn = None
        return return_code

    async def readline(self):
        """Read next incoming line from the connection.
        """
        return await self._input.readline()

    def write(self, data):
        """Write data to the connection.
        """
        self._output.write(data)

    async def drain(self):
        """Wait while the output buffer is flushed.
        """
        LOGGER.info('libofp connection drain: buffer_size=%d',
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
