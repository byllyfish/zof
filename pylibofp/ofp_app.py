"""Main ofp_app functions."""

import asyncio
from .controller import Controller
from .controllerapp import ControllerApp
from .appfacade import AppFacade
from .logging import init_logging
from .compiledmessage import CompiledMessage

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


def ofp_run(*,
            loop=None,
            listen_endpoints=_LISTEN_ENDPOINTS,
            libofp_args=None,
            loglevel='info',
            security=None,
            command_shell=True):
    """Run event loop for ofp_app's.

    Args:
        loop (Optional[asyncio.EventLoop]): Run asyncio tasks on this event loop
            until complete. If None, use default event loop.
        listen_endpoints (Optional[List[str]]): Default endpoints to listen on.
            If None or empty, don't listen by default.
        libofp_args (Optional[List[str]]): Command line arguments to libofp.
        loglevel (Optional[str]): Default log level (info). If None, logging is
            left unconfigured.
        security (Optional[Dict[str, str]]): Dictionary with security settings
            for libofp connections:
                - "cert": SSL Certificate with Private Key (PEM)
                - "cafile": CA Certificate (PEM)
                - "password": Password for "cert", if needed.
        command_shell (bool): If true, load the built-in command_shell app.
    """
    if not loop:
        loop = asyncio.get_event_loop()

    if command_shell:
        import pylibofp.service.command_shell

    if loglevel:
        init_logging(loglevel)

    controller = Controller.singleton()
    controller.run_loop(
        loop=loop,
        listen_endpoints=listen_endpoints,
        libofp_args=libofp_args,
        security=security)


def ofp_compile(msg):
    """Compile an OpenFlow message template.
    """
    controller = Controller.singleton()
    return CompiledMessage(controller, msg)
