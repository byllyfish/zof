"""Implements a list of async tasks."""

import asyncio

from zof.log import logger


class TaskList:
    """Manages a collection of async tasks that can be cancelled.

    A TaskList is designed to manage tasks associated with some scope.
    You can create a task that is tied to a scope. When the scope
    ends, you can automatically cancel all of its tasks.

    The task list contains the running tasks. When a task finishes, it
    removes itself from the list. Any exceptions raises by a task
    are directed to a specified handler.

    The primary API is synchronous:

        create_task - create a task and add it to the list.
        cancel - cancel all tasks in the list.
    """

    def __init__(self, loop, on_exception=None):
        """Initialize an empty task list."""
        assert (on_exception is None
                or not asyncio.iscoroutinefunction(on_exception))
        self._loop = loop
        self._tasks = set()
        self.on_exception = on_exception

    def create_task(self, coro):
        """Create a managed async task for a coroutine."""
        assert asyncio.iscoroutine(coro)
        task = self._loop.create_task(coro)
        task.add_done_callback(self._task_done)
        self._tasks.add(task)
        logger.debug('Task create %r', task)
        return task

    def _task_done(self, task):
        """Handle task cleanup."""
        logger.debug('Task done %r', task)
        self._tasks.discard(task)
        try:
            exc = task.exception()
            if exc and self.on_exception:
                self.on_exception(exc)
        except asyncio.CancelledError:
            pass

    def cancel(self):
        """Cancel all managed async tasks."""
        for task in self._tasks:
            logger.debug('Task cancel %r', task)
            task.cancel()

    async def wait_cancelled(self, timeout=1.0):
        """Wait for cancelled tasks to complete."""
        if self._tasks:
            _, pending = await asyncio.wait(self._tasks, timeout=timeout)
            if pending:
                raise RuntimeError(
                    'TaskList: Tasks did not exit as expected: %r' % pending)

    def __len__(self):
        """Return length of task list."""
        return len(self._tasks)

    def __contains__(self, task):
        """Return true if task is in list."""
        return task in self._tasks

    def __iter__(self):
        """Return iterable for task list."""
        return iter(self._tasks)
