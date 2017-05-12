import collections
import logging.config
import os
import warnings
import sys

EXT_STDERR = 'ext://stderr'

default_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger_name = __package__

_logging_inited = False

_stderr_handler = logging.StreamHandler(sys.stderr)
_stderr_handler.setFormatter(default_formatter)


class TailBufferedHandler(logging.Handler):
    """Logging handler that records the last N log records."""

    def __init__(self, maxlen=10):
        super().__init__()
        self._tail = collections.deque(maxlen=maxlen)

    def lines(self):
        """Return last N log lines."""
        return self._tail

    def emit(self, record):
        """Log the specified log record."""
        try:
            self._tail.append(self.format(record))
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)

    def close(self):
        """Close the log handler."""
        super().close()
        self._tail.clear()

    @staticmethod
    def install():
        """Install tail logging handler."""
        handler = TailBufferedHandler()
        handler.setFormatter(default_formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        return handler


class PatchedConsoleHandler(logging.Handler):
    """Logging handler that writes to stdout EVEN when stdout is patched.

    The normal StreamHandler grabs a reference to `sys.stdout` once at
    initialization time. This class always logs to the current sys.stdout
    which may be patched at runtime by prompt_toolkit.

    This class disables the default StreamHandler if it is logging to stderr.
    """

    def emit(self, record):
        try:
            self.write(self.format(record))
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)

    def write(self, line):  # pylint: disable=no-self-use
        stream = sys.stdout
        stream.write(line)
        stream.write('\n')

    @staticmethod
    def install():
        """Install stdout logging handler.

        Change level of default stderr logging handler.
        """
        handler = PatchedConsoleHandler()
        handler.setFormatter(default_formatter)
        handler.setLevel('WARNING')
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        # From now on, only log critical events to stderr.
        _stderr_handler.setLevel('CRITICAL')
        return handler


def init_logging(loglevel, logfile=EXT_STDERR):
    """Set up logging.

    This routine enables asyncio debug mode if `loglevel` is 'debug'.
    """
    global _logging_inited  # pylint: disable=global-statement
    if _logging_inited:
        # Make sure we only initialize logging once.
        return
    _logging_inited = True

    if loglevel.lower() == 'debug':
        os.environ['PYTHONASYNCIODEBUG'] = '1'

    _make_default_loggers(loglevel, logfile)

    logging.captureWarnings(True)
    warnings.simplefilter('always')


def _make_default_loggers(loglevel, logfile):
    """Prepare the default loggers.
    """
    root_logger = logging.getLogger()
    root_logger.addHandler(_stderr_handler)

    if logfile and logfile != EXT_STDERR:
        logfile_handler = _make_logfile_handler(logfile)
        logfile_handler.setFormatter(default_formatter)
        root_logger.addHandler(logfile_handler)
        # When there is a log file, only log critical events to stderr.
        _stderr_handler.setLevel('CRITICAL')

    ofp_logger = logging.getLogger(logger_name)
    ofp_logger.setLevel(loglevel.upper())

    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.setLevel('WARNING')


def _make_logfile_handler(logfile):
    """Return log file handler."""
    return logging.handlers.RotatingFileHandler(
        logfile, maxBytes=2**20, backupCount=10, encoding='utf8')
