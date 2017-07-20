"""
Environment Variables:

    OFP_APP_DEBUG            Debug mode.
"""

import sys
from .api_args import common_args, import_modules
from .controller import Controller
from .logging import init_logging


def run(*, args=None):
    """Run event loop for ofp_app.

    Args:
        args (Optional[argparse.Namespace]): Arguments derived from 
            ArgumentParser. If None, use `common_args` parser.
    """
    if args is None:
        args = common_args().parse_args()

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
        exit_status = controller.run_loop(args=args)
    finally:
        Controller.destroy()

    if not args.x_under_test:
        sys.exit(exit_status)

    return exit_status
