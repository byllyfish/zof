"""Main ofp_app functions."""

from .controller import Controller
from .controllerapp import ControllerApp
from .appfacade import AppFacade
from .logging import init_logging
from .compiledmessage import CompiledMessage, CompiledObject

_LISTEN_ENDPOINTS = (6633, 6653)


def ofp_app(name, *, ofversion=None, kill_on_exception=False):
    """Construct a new app.

    Args:
        name (str): Name of the app.
        ofversion (Optional[int]): Supported OpenFlow versions.

    Returns:
        AppFacade: API object for app.
    """
    controller = Controller.singleton()
    app = ControllerApp(
        controller,
        name=name,
        ofversion=ofversion,
        kill_on_exception=kill_on_exception)
    return AppFacade(app)


def ofp_run(*,
            listen_endpoints=_LISTEN_ENDPOINTS,
            oftr_args=None,
            loglevel='info',
            security=None,
            command_shell=True):
    """Run event loop for ofp_app's.

    Args:
        listen_endpoints (Optional[List[str]]): Default endpoints to listen on.
            If None or empty, don't listen by default.
        oftr_args (Optional[List[str]]): Command line arguments to oftr.
        loglevel (Optional[str]): Default log level (info). If None, logging is
            left unconfigured.
        security (Optional[Dict[str, str]]): Dictionary with security settings
            for oftr connections:
                - "cert": SSL Certificate with Private Key (PEM)
                - "cafile": CA Certificate (PEM)
                - "password": Password for "cert", if needed.
        command_shell (bool): If true, load the built-in command_shell app.
    """
    if command_shell:
        # pylint: disable=cyclic-import
        import pylibofp.service.command_shell as _

    if loglevel:
        init_logging(loglevel)

    controller = Controller.singleton()
    controller.run_loop(
        listen_endpoints=listen_endpoints,
        oftr_args=oftr_args,
        security=security)


def ofp_compile(msg):
    """Compile an OpenFlow message template.
    """
    controller = Controller.singleton()
    if isinstance(msg, str):
        return CompiledMessage(controller, msg)
    else:
        return CompiledObject(controller, msg)
