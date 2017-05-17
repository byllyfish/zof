"""Main ofp_app API.

- ofp_app
- ofp_run
- ofp_compile

Environment Variables:

    OFP_APP_LOGLEVEL            Default logging mode.
    OFP_APP_OFTR_PREFIX         Prefix used to launch oftr. Used for tools
                                like valgrind or strace.
    OFP_APP_OFTR_PATH           Path to oftr version to use.
    OFP_APP_OFTR_ARGS           Arguments passed to oftr.
    OFP_APP_UVLOOP              Set to true to use uvloop.
"""

import os
import asyncio

from .controller import Controller
from .controllerapp import ControllerApp
from .appfacade import AppFacade
from .compiledmessage import CompiledMessage, CompiledObject
from .logging import init_logging, EXT_STDERR

if os.environ.get('OFP_APP_LOGLEVEL'):
    init_logging(os.environ.get('OFP_APP_LOGLEVEL'))

_LISTEN_ENDPOINTS = (6633, 6653)


def ofp_app(name, *, kill_on_exception=False, precedence=1000):
    """Construct a new app.

    Args:
        name (str): Name of the app.
        kill_on_exception (Optiona[bool]): Abort if app raises exception.
        precedence (Optional[int]): Precedence for event dispatch

    Returns:
        AppFacade: API object for app.
    """
    controller = Controller.singleton()
    app = ControllerApp(
        controller,
        name=name,
        kill_on_exception=kill_on_exception,
        precedence=precedence)
    return AppFacade(app)


def ofp_run(*,
            listen_endpoints=_LISTEN_ENDPOINTS,
            listen_versions=None,
            oftr_options=None,
            loglevel='info',
            logfile=EXT_STDERR,
            security=None):
    """Run event loop for ofp_app's.

    Args:
        listen_endpoints (Optional[List[str]]): Default endpoints to listen on.
            If None or empty, don't listen by default.
        listen_versions (Optional[List[int]]): Acceptible OpenFlow protocol 
            versions. If None or empty, accept all versions.
        oftr_options (Optional[Dict[str, str]]): Dictionary with settings for
            launching oftr process.
                - "path": Path to oftr executable (default=`which oftr`)
                - "args": Command line arguments to oftr (default='')
                - "prefix": Prefix before command line (default='')
                - "subcmd": oftr sub-command (default='jsonrpc')
        loglevel (Optional[str]): Default log level (info). If None, logging is
            left unconfigured.
        logfile (Optional[str]): Log file.
        security (Optional[Dict[str, str]]): Dictionary with security settings
            for oftr connections:
                - "cert": SSL Certificate with Private Key (PEM)
                - "cafile": CA Certificate (PEM)
                - "password": Password for "cert", if needed.
    """
    if loglevel:
        init_logging(loglevel, logfile)

    if not oftr_options:
        oftr_options = {
            'path': os.environ.get('OFP_APP_OFTR_PATH'),
            'args': os.environ.get('OFP_APP_OFTR_ARGS'),
            'prefix': os.environ.get('OFP_APP_OFTR_PREFIX')
        }

    if os.environ.get('OFP_APP_UVLOOP'):
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    controller = Controller.singleton()
    controller.run_loop(
        listen_endpoints=listen_endpoints,
        listen_versions=listen_versions,
        oftr_options=oftr_options,
        security=security)


def ofp_compile(msg):
    """Compile an OpenFlow message template."""
    controller = Controller.singleton()
    if isinstance(msg, str):
        return CompiledMessage(controller, msg)
    else:
        return CompiledObject(controller, msg)
