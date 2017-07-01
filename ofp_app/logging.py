import logging.config
import os
import warnings
import sys

EXT_STDERR = 'ext://stderr'

default_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s')

_logging_inited = False

stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setFormatter(default_formatter)


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
    if not root_logger.hasHandlers():
        root_logger.addHandler(stderr_handler)

    if logfile and logfile != EXT_STDERR:
        logfile_handler = _make_logfile_handler(logfile)
        logfile_handler.setFormatter(default_formatter)
        root_logger.addHandler(logfile_handler)
        # When there is a log file, only log critical events to stderr.
        stderr_handler.setLevel('CRITICAL')

    ofp_logger = logging.getLogger(__package__)
    ofp_logger.setLevel(loglevel.upper())

    asyncio_logger = logging.getLogger('asyncio')
    asyncio_logger.setLevel('WARNING')


def _make_logfile_handler(logfile):
    """Return log file handler."""
    return logging.handlers.RotatingFileHandler(
        logfile, maxBytes=2**20, backupCount=10, encoding='utf8')
