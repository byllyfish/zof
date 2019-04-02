"""Backport asyncio functions for Python 3.6 compatibility."""

import asyncio
import sys


def asyncio_run(coro, *, debug=False):
    """Backport of asyncio.run() for Python 3.6 support."""
    loop = asyncio.get_event_loop()

    try:
        loop.set_debug(debug)
        return loop.run_until_complete(coro)
    finally:
        _shutdown_loop(loop)


def _shutdown_loop(loop):
    try:
        _cancel_all_tasks(loop)
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()


def _cancel_all_tasks(loop):
    # Adapted from Python 3.7 stdlib.
    to_cancel = asyncio.Task.all_tasks(loop)
    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        asyncio.gather(*to_cancel, loop=loop, return_exceptions=True))

    for task in to_cancel:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'unhandled exception during asyncio.run() shutdown',
                'exception': task.exception(),
                'task': task,
            })


if sys.version_info >= (3, 7):
    # pylint: disable=no-member
    asyncio_run = asyncio.run  # type: ignore
    get_running_loop = asyncio.get_running_loop  # type: ignore
    current_task = asyncio.current_task  # type: ignore

else:
    get_running_loop = asyncio.get_event_loop
    current_task = asyncio.Task.current_task
