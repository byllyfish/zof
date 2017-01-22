import signal
import asyncio
import functools


DEFAULT_SIGNALS = ('SIGINT', 'SIGHUP', 'SIGTERM')


def run_server(loop, *, signals=DEFAULT_SIGNALS, signal_handler, pending_timeout=5.0):
    """Run asyncio event loop for server.
    """
    # Install signal handler function(s).
    for signame in signals:
        loop.add_signal_handler(getattr(signal, signame), functools.partial(signal_handler, signame))

    # Run loop until stopped with `loop.stop()`
    loop.run_forever()

    # TODO(bfish): Handle py3.6 async generator cleanup?

    # Try 3 times to finish our pending tasks. This gives stopping tasks
    # a chance to create more async tasks to clean up.
    for _ in range(3):
        if not _run_pending(loop, pending_timeout):
            break

    loop.close()


def _run_pending(loop, pending_timeout):
    """Run until pending tasks are complete.

    Return true if we still have more pending tasks.
    """
    try:
        pending = asyncio.Task.all_tasks()
        loop.run_until_complete(asyncio.wait(pending, timeout=pending_timeout))
        return False
    except RuntimeError as ex:
        # `run_until_complete` throws an exception if new async tasks are
        # started by the pending tasks. Return true when this happens.
        if str(ex) == 'Event loop stopped before Future completed.':
            return True
        raise
