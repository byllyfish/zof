import signal
import asyncio
import functools

DEFAULT_SIGNALS = ('SIGINT', 'SIGHUP', 'SIGTERM')


def _default_signal_handler(_signame):
    asyncio.get_event_loop().stop()


def run_server(*,
               signals=DEFAULT_SIGNALS,
               signal_handler=_default_signal_handler,
               pending_timeout=5.0,
               logger=None):
    """Run asyncio event loop for server.

    This function handles the boilerplate for running an async server:

      - handling signals
      - shutting down asynchronously
      - closing the loop

    Example::

        async def task():
            await asyncio.sleep(3)
            asyncio.get_event_loop().stop()

        asyncio.ensure_future(task())
        run_server()
    """
    loop = asyncio.get_event_loop()
    assert not loop.is_closed()

    # Install signal handler function(s).
    if signal_handler:
        for signame in signals:
            loop.add_signal_handler(
                getattr(signal, signame),
                functools.partial(signal_handler, signame))

    try:
        if logger:
            logger.debug('run_server started: %r',
                         asyncio.Task.all_tasks(loop))
        # Run loop until stopped with `loop.stop()`.
        loop.run_forever()

    except KeyboardInterrupt:
        pass

    finally:
        _shutdown_pending(loop, pending_timeout, logger)
        if hasattr(loop, 'shutdown_asyncgens'):
            if logger:
                logger.debug('run_server shutdown_asyncgens')
            loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        if logger:
            logger.debug('run_server stopped')


def _shutdown_pending(loop, pending_timeout, logger):
    """Give pending tasks a chance to exit cleanly.

    Try 3 times to finish our pending tasks. This gives stopping tasks
    a chance to create more async tasks during shutdown.
    """
    if logger:
        logger.debug('run_server: shutdown pending')
    for _ in range(3):
        if not _run_pending(loop, pending_timeout, logger):
            break
    if logger:
        tasks = _running_tasks(loop)
        if tasks:
            logger.warning('run_server: shutdown completed: %d tasks:\n  %s',
                           len(tasks), '\n  '.join(repr(t) for t in tasks))
        else:
            logger.debug('run_server: shutdown completed')


def _run_pending(loop, pending_timeout, logger):
    """Run until pending tasks are complete.

    Return true if we still have more pending tasks.
    """
    try:
        pending = asyncio.Task.all_tasks(loop)
        if pending:
            if logger:
                logger.debug('run_server: run_pending %r', pending)
            loop.run_until_complete(
                asyncio.wait(
                    pending, timeout=pending_timeout))
            return True
    except RuntimeError as ex:
        # `run_until_complete` throws an exception if new async tasks are
        # started by the pending tasks *and* they are still running when the
        # original tasks complete. Return true when this happens.
        if str(ex) == 'Event loop stopped before Future completed.':
            return True
        raise
    return False


def _running_tasks(loop):
    # pylint: disable=protected-access
    tasks = asyncio.Task.all_tasks(loop)
    return [t for t in tasks if t._state not in ('FINISHED', 'CANCELLED')]
