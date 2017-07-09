"""
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
from .logging import init_logging, EXT_STDERR

if os.environ.get('OFP_APP_LOGLEVEL'):
    init_logging(os.environ.get('OFP_APP_LOGLEVEL'))

_LISTEN_ENDPOINTS = [6653]


def run(*,
            listen_endpoints='default',
            listen_versions=None,
            oftr_options=None,
            loglevel=None,
            logfile=None,
            security=None,
            args=None):
    """Run event loop for ofp_app.

    Args:
        listen_endpoints (str|List[str]): Endpoints to listen on.
            If None, don't listen. If "default", listen on default port.
        listen_versions (List[int]): Acceptible OpenFlow protocol
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
                - "cert": SSL Certificate Chain (PEM)
                - "cacert": CA Certificate (PEM)
                - "privkey": Private Key (PEM)
                - "password": Password for "privkey", if needed.
        args (Optional[argparse.Namespace]): Arguments from `ofp_common_args`
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

    if args and security is None:
        security = {
            'cert': args.cert,
            'cacert': args.cacert,
            'privkey': args.privkey
        }
        if not any(security.values()):
            security = None

    if loglevel:
        init_logging(loglevel, logfile)

    if not oftr_options:
        oftr_options = {
            'path': os.environ.get('OFP_APP_OFTR_PATH'),
            'args': os.environ.get('OFP_APP_OFTR_ARGS'),
            'prefix': os.environ.get('OFP_APP_OFTR_PREFIX')
        }

    if os.environ.get('OFP_APP_UVLOOP'):
        import uvloop  # pylint: disable=import-error
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    controller = Controller.singleton()
    controller.run_loop(
        listen_endpoints=listen_endpoints,
        listen_versions=listen_versions,
        oftr_options=oftr_options,
        security=security)


def _arg(args, key, default=None):
    if args is None:
        return default
    return getattr(args, key, None) or default