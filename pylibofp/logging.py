import collections
import logging.config
import os
import warnings
import sys


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
        except Exception: # pylint: disable=broad-except
            self.handleError(record)

    def close(self):
        """Close the log handler."""
        super().close()
        self._tail.clear()

    @staticmethod
    def install():
        """Install tail logging handler."""
        root_logger = logging.getLogger()
        handler = TailBufferedHandler()
        handler.setFormatter(root_logger.handlers[0].formatter)
        root_logger.addHandler(handler)


class PatchedConsoleHandler(logging.Handler):
    """Logging handler that writes to stdout EVEN when stdout is patched.

    The normal StreamHandler grabs a reference to `sys.stdout` once at 
    initialization time. This class always logs to the current sys.stdout 
    which may be patched at runtime by prompt_toolkit.
    """

    def emit(self, record):
        try:
            self.write(self.format(record))
        except Exception: # pylint: disable=broad-except
            self.handleError(record)

    def write(self, line):
        stream = sys.stdout
        stream.write(line)
        stream.write('\n')

    @staticmethod
    def install():
        """Install stdout logging handler."""
        root_logger = logging.getLogger()
        handler = PatchedConsoleHandler()
        handler.setFormatter(root_logger.handlers[0].formatter)
        handler.setLevel('WARNING')
        root_logger.addHandler(handler)


def init_logging(loglevel):
    """Set up logging.

    This routine also enables asyncio debug mode if `loglevel` is 'debug'.
    """
    if loglevel.lower() == 'debug':
        os.environ['PYTHONASYNCIODEBUG'] = '1'

    # Set up basic logging from config.
    logging.config.dictConfig(_logging_config(loglevel))

    # Create two more output handlers at runtime.
    PatchedConsoleHandler.install()
    TailBufferedHandler.install()

    logging.captureWarnings(True)
    warnings.simplefilter('always')


def find_log_handler(class_):
    """Find log handler by class.
    """
    root_logger = logging.getLogger()
    return next(h for h in root_logger.handlers if isinstance(h, class_))


def _logging_config(loglevel):
    """Construct dictionary to configure logging via `dictConfig`.
    """
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'complete': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            }
        },
        'handlers': {
            'logfile': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'complete',
                'filename': 'ofp_app.log',
                'maxBytes': 2**20,
                'backupCount': 20,
                'encoding': 'utf8'
            }
        },
        'loggers': {
            'pylibofp': {
                'level': loglevel.upper()
            },
            'asyncio': {
                'level': 'WARNING'  # avoid polling msgs at 'INFO' level
            }
        },
        'root': {
            'handlers': ['logfile']
        }
    }
