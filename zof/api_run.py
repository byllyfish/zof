"""
Environment Variables:

    zof_DEBUG            Debug mode.
"""

import sys
from .api_args import common_args
from .controller import Controller
from .logging import init_logging


def run(*, args=None, apps=None):
    """Run event loop for zof.

    Args:
        args (Optional[argparse.Namespace]): Arguments derived from
            ArgumentParser. If None, use `common_args` parser.
        apps (List[zof.Application]): List of apps to run. If empty, use
            list of registered apps.
    """
    if args is None:
        args = common_args(include_x_modules=True).parse_args()

    if args.loglevel:
        init_logging(args.loglevel, args.logfile)

    if args.x_uvloop:
        import uvloop  # pylint: disable=import-error
        import asyncio
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    controller = Controller.singleton()
    exit_status = controller.run_loop(args=args, apps=apps)

    if not args.x_under_test:
        sys.exit(exit_status)

    return exit_status
