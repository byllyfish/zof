"""Main ofp_app API.

- ofp_app
- ofp_run
- ofp_compile

Environment Variables:

    OFP_APP_LOGLEVEL            Default logging mode.
    OFP_APP_OFTR_PREFIX         Prefix used to launch oftr. Used for tools
                                like valgrind, strace, or catchsegv.
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

_LISTEN_ENDPOINTS = [6653]


def ofp_app(name, *, kill_on_exception=False, precedence=1000):
    """Construct a new app.

    Args:
        name (str): Name of the app.
        kill_on_exception (bool|str): Abort if app raises exception. If this
            value is a string, it's treated as the name of the exception log.
        precedence (int): Precedence for event dispatch

    Returns:
        AppFacade: API object for app.
    """
    controller = Controller.singleton()
    if controller.find_app(name):
        raise ValueError('App named "%s" already exists.' % name)
    app = ControllerApp(
        controller,
        name=name,
        kill_on_exception=kill_on_exception,
        precedence=precedence)
    return AppFacade(app)


def ofp_run(*,
            listen_endpoints='default',
            listen_versions=None,
            oftr_options=None,
            loglevel=None,
            logfile=None,
            security=None,
            args=None):
    """Run event loop for ofp_app.

    Args:
        listen_endpoints (Optional[List[str]]): Endpoints to listen on.
            If None, don't listen. If "default", listen on default port.
        listen_versions (Optional[List[int]]): Acceptible OpenFlow protocol 
            versions. If None or empty, accept all versions.
        oftr_options (Optional[Dict[str, str]]): Dictionary with settings for
            launching oftr process.
                - "path": Path to oftr executable (default=`which oftr`)
                - "args": Command line arguments to oftr (default='')
                - "prefix": Prefix before command line (default='')
                - "subcmd": oftr sub-command (default='jsonrpc')
        loglevel (Optional[str]): Log level (info). If None, logging is
            left unconfigured.
        logfile (Optional[str]): Log file.  Defaults to stderr.
        security (Optional[Dict[str, str]]): Dictionary with security settings
            for oftr connections:
                - "cert": SSL Certificate with Private Key (PEM)
                - "cafile": CA Certificate (PEM)
                - "password": Password for "cert", if needed.
        args (Optional[argparse.Namespace]): Arguments from `ofp_default_args`
            ArgumentParser.
    """
    if listen_endpoints is None:
        listen_endpoints = _arg(args, 'listen_endpoints')
    elif listen_endpoints == 'default':
        listen_endpoints = _arg(args, 'listen_endpoints', _LISTEN_ENDPOINTS)

    if loglevel is None:
        loglevel = _arg(args, 'loglevel', 'info')

    if logfile is None:
        logfile = _arg(args, 'logfile', EXT_STDERR)

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


def _arg(args, key, default=None):
    if args is None:
        return default
    return getattr(args, key, None) or default
