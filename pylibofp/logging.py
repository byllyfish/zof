import collections
import logging.config
import os
import warnings


class TailBufferedHandler(logging.Handler):
    """Logging handler that records the last N log records.
    """
    _singleton = None

    def __init__(self, maxlen=10):
        super().__init__()
        self._tail = collections.deque(maxlen=maxlen)

    def lines(self):
        """Generator for last N log lines.
        """
        for record in self._tail:
            try:
                yield self.format(record)
            except Exception:
                self.handleError(record)

    def emit(self, record):
        """Log the specified log record.
        """
        self._tail.append(record)

    def close(self):
        """Close the log handler.
        """
        super().close()
        self._tail.clear()


    @staticmethod
    def install():
        """Install tail logging handler.
        """
        # Only install it once.
        if TailBufferedHandler._singleton:
            return
        handler = TailBufferedHandler()
        root_logger = logging.getLogger()
        handler.setFormatter(root_logger.handlers[0].formatter)
        root_logger.addHandler(handler)
        TailBufferedHandler._singleton = handler

    @staticmethod
    def tail():
        """Return last N lines.
        """
        return TailBufferedHandler._singleton.lines()


def init_logging(loglevel):
    """Set up logging.

    This routine also enables asyncio debug mode if `loglevel` is 'debug'.
    """
    if loglevel.lower() == 'debug':
        os.environ['PYTHONASYNCIODEBUG'] = '1'

    logging.config.dictConfig(_logging_config(loglevel))
    TailBufferedHandler.install()

    logging.captureWarnings(True)
    warnings.simplefilter('always')


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
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'complete',
                'level': 'WARNING',
                "stream": "ext://sys.stdout"
            },
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
            'handlers': ['console', 'logfile']
        }
    }
