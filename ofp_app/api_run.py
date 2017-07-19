"""
Environment Variables:

    OFP_APP_DEBUG            Debug mode.
"""

from .api_args import common_args, import_modules
from .controller import Controller
from .logging import init_logging


def run(*, args=None, under_test=False):
    """Run event loop for ofp_app.

    Args:
        args (Optional[argparse.Namespace]): Arguments derived from 
            ArgumentParser. If None, use `common_args` parser.
        under_test (Boolean): Set to true when you are running this function
            as part of a unit test.
    """
    if args is None:
        args = common_args(under_test=under_test).parse_args()

    if args.loglevel:
        init_logging(args.loglevel, args.logfile)

    if args.x_modules:
        import_modules(args.x_modules)

    if args.x_uvloop:
        import uvloop  # pylint: disable=import-error
        import asyncio
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    try:
        controller = Controller.singleton()
        controller.run_loop(args=args, under_test=under_test)
    finally:
        Controller.destroy()
