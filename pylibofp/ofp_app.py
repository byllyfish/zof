"""Main ofp_app functions."""

import asyncio
import os
import warnings
import logging.config
from .controller import Controller
from .controllerapp import ControllerApp
from .appfacade import AppFacade

_LISTEN_ENDPOINTS = (6633, 6653)

def ofp_app(name, *, ofversion=None):
    """Construct a new app.

    Args:
        name (str): Name of the app.
        ofversion (Optional[str]): Supported OpenFlow versions.
            Example values: 
                - "1.0" = OpenFlow 1.0 only.
                - "1.3+" = OpenFlow 1.3 and later.
                - "1.0, 1.3+" = OpenFlow 1.0 along with OF 1.3 and later.

    Returns:
        AppFacade: API object for app.
    """
    controller = Controller.singleton()
    app = ControllerApp(controller, name=name, ofversion=ofversion)
    return AppFacade(app)


def ofp_run(*, loop=None, listen_endpoints=_LISTEN_ENDPOINTS, libofp_args=None, loglevel='info', security=None):
    """Run event loop for ofp_app's.

    Args:
        loop (Optional[asyncio.EventLoop]): Run asyncio tasks on this event loop
            until complete. If None, use default event loop.
        listen_endpoints (Optional[List[str]]): Default endpoints to listen on.
            If None or empty, don't listen by default.
        libofp_args (Optional[List[str]]): Command line arguments to libofp.
        loglevel (Optional[str]): Default log level. If None, logging is not 
            configured.
        security (Optional[Dict[str, str]]): Dictionary with security settings
            for libofp connections:
                - "cert": SSL Certificate with Private Key (PEM)
                - "cafile": CA Certificate (PEM)
                - "password": Password for "cert", if needed.
    """
    if not loop:
        loop = asyncio.get_event_loop()
    if loglevel:
        _init_logging(loglevel)
    Controller.singleton().run_loop(loop=loop, listen_endpoints=listen_endpoints, libofp_args=libofp_args, security=security)



def _init_logging(loglevel):
    """Set up logging.

    This routine also enables asyncio debug mode if `loglevel` is 'debug'.
    """
    if loglevel.lower() == 'debug':
        os.environ['PYTHONASYNCIODEBUG'] = '1'

    logging.config.dictConfig(_logging_config(loglevel))
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
                'formatter': 'complete'
            }
        },
        'loggers': {
            'pylibofp': {
                'level': loglevel.upper()
            },
            #'pylibofp.app': {
            #    'level': loglevel.upper()
            #},
            'asyncio': {
                'level': 'WARNING'  # avoid polling msgs at 'INFO' level
            }
        },
        'root': {
            'handlers': ['console']
        }
    }
