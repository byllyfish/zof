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
            logfile=None,
            security=None,
            command_prompt='ofp_app> '):
    """Run event loop for ofp_app's.

    Args:
        listen_endpoints (Optional[List[str]]): Default endpoints to listen on.
            If None or empty, don't listen by default.
        oftr_args (Optional[List[str]]): Command line arguments to oftr.
        loglevel (Optional[str]): Default log level (info). If None, logging is
            left unconfigured.
        logfile (Optional[str]): Log file.
        security (Optional[Dict[str, str]]): Dictionary with security settings
            for oftr connections:
                - "cert": SSL Certificate with Private Key (PEM)
                - "cafile": CA Certificate (PEM)
                - "password": Password for "cert", if needed.
        command_prompt (Optional[str]): Show interactive command prompt.
    """
    if command_prompt:
        from pylibofp.service import command_shell
        command_shell.ofp.command_prompt = command_prompt
    elif not logfile:
        # If there's no command shell or logfile, send log to stderr.
        logfile = 'ext://stderr'

    if loglevel:
        init_logging(loglevel, logfile)

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
