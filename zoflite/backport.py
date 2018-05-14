"""Backported asyncio functions."""

import asyncio


def asyncio_run(coro, *, debug=False):
    """Backport of Python 3.7's `asyncio.run()` API.

    This code is strict about not leaving any dangling tasks. The real
    implementation (in Python 3.7) cancels them.

    Adapted from https://github.com/python/cpython/blob/master/Lib/asyncio/runners.py
    on 9 May 2018.
    """

    assert asyncio._get_running_loop() is None  # pylint: disable=no-member,protected-access
    assert asyncio.iscoroutine(coro), repr(coro)

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.set_debug(debug)
        return loop.run_until_complete(coro)
    finally:
        try:
            assert not asyncio.Task.all_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
