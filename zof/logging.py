import logging.config
import os
import warnings
import sys

EXT_STDERR = 'ext://stderr'

DEFAULT_FORMATTER = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s')

STDERR_HANDLER = logging.StreamHandler(sys.stderr)
STDERR_HANDLER.setFormatter(DEFAULT_FORMATTER)

_LOGGING_INITED = False


def init_logging(loglevel, logfile=EXT_STDERR):
    """Set up logging.

    This method attaches log handlers to the root logger:
        - a stderr handler (only if the root logger has no other handlers)
        - a file handler if specified

    When a logfile is specified, the stderr handler will only log critical
    events.

    This routine enables asyncio debug mode if `loglevel` is 'debug'.
    """
    global _LOGGING_INITED  # pylint: disable=global-statement
    if _LOGGING_INITED:
        # Make sure we only initialize logging once.
        set_loglevel(loglevel)
        return
    _LOGGING_INITED = True

    _make_default_handlers(logfile)

    set_loglevel(loglevel)
    logging.captureWarnings(True)
    warnings.simplefilter('always')

    if loglevel.lower() == 'debug':
        os.environ['PYTHONASYNCIODEBUG'] = '1'

    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.setLevel('WARNING')


def set_loglevel(loglevel):
    """Change current log level.
    """
    ofp_logger = logging.getLogger(__package__)
    ofp_logger.setLevel(loglevel.upper())


def _make_default_handlers(logfile):
    """Prepare the default loggers.
    """
    root_logger = logging.getLogger()
    if not root_logger.hasHandlers():
        root_logger.addHandler(STDERR_HANDLER)

    if logfile and logfile != EXT_STDERR:
        logfile_handler = _make_logfile_handler(logfile)
        logfile_handler.setFormatter(DEFAULT_FORMATTER)
        root_logger.addHandler(logfile_handler)
        # When there is a log file, only log critical events to stderr.
        STDERR_HANDLER.setLevel('CRITICAL')


def _make_logfile_handler(logfile):
    """Return log file handler."""
    return logging.handlers.RotatingFileHandler(
        logfile, maxBytes=2**20, backupCount=10, encoding='utf8')
