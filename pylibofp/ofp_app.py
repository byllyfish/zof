"""Main ofp_app API.

- ofp_app
- ofp_run
- ofp_compile

Environment Variables:

    OFP_APP_DEBUG               If true, activates debug logging mode.
    OFP_APP_IMPORT_MODULES      Command-separated list of additional modules
                                to load.
    OFP_APP_OFTR_PREFIX         Prefix used to launch oftr. Used for tools
                                like valgrind or strace.
    OFP_APP_OFTR_PATH           Path to oftr version to use.
    OFP_APP_OFTR_ARGS           Arguments passed to oftr.

"""

import os

from .controller import Controller
from .controllerapp import ControllerApp
from .appfacade import AppFacade
from .compiledmessage import CompiledMessage, CompiledObject
from .logging import init_logging, EXT_STDERR

if os.environ.get('OFP_APP_DEBUG'):
    init_logging('debug')

_LISTEN_ENDPOINTS = (6633, 6653)


def ofp_app(name, *, ofversion=None, kill_on_exception=False, precedence=1000):
    """Construct a new app.

    Args:
        name (str): Name of the app.
        ofversion (Optional[int]): Supported OpenFlow versions.
        kill_on_exception (Optiona[bool]): Abort if app raises exception.
        precedence (Optional[int]): Precedence for event dispatch

    Returns:
        AppFacade: API object for app.
    """
    controller = Controller.singleton()
    app = ControllerApp(
        controller,
        name=name,
        ofversion=ofversion,
        kill_on_exception=kill_on_exception,
        precedence=precedence)
    return AppFacade(app)


def ofp_run(*,
            listen_endpoints=_LISTEN_ENDPOINTS,
            oftr_options=None,
            loglevel='info',
            logfile=EXT_STDERR,
            security=None):
    """Run event loop for ofp_app's.

    Args:
        listen_endpoints (Optional[List[str]]): Default endpoints to listen on.
            If None or empty, don't listen by default.
        oftr_options (Optional[Dict[str, str]]): Dictionary with settings for
            oftr process.
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

    # Allow late specification of python modules to load.
    import_list = os.environ.get('OFP_APP_IMPORT_MODULES')
    if import_list:
        _import_modules(import_list)

    if not oftr_options:
        oftr_options = {
            'path': os.environ.get('OFP_APP_OFTR_PATH'),
            'args': os.environ.get('OFP_APP_OFTR_ARGS'),
            'prefix': os.environ.get('OFP_APP_OFTR_PREFIX')
        }

    controller = Controller.singleton()
    controller.run_loop(
        listen_endpoints=listen_endpoints,
        oftr_options=oftr_options,
        security=security)


def ofp_compile(msg):
    """Compile an OpenFlow message template."""
    controller = Controller.singleton()
    if isinstance(msg, str):
        return CompiledMessage(controller, msg)
    else:
        return CompiledObject(controller, msg)


def _import_modules(import_list):
    import importlib
    # FIXME(bfish): Handle source files and local modules.
    for module in import_list.split(','):
        importlib.import_module(module)
