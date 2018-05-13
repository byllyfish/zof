"""Implements a set of async tasks."""

import asyncio
import logging

LOGGER = logging.getLogger(__package__)


class TaskSet:
    """Manages a collection of async tasks that can be cancelled."""

    def __init__(self, loop):
        self._loop = loop
        self._tasks = set()

    def create_task(self, coro):
        """Create a managed async task for a coroutine."""

        # When a task is cancelled, it should be removed from `self._tasks`
        # within 1-2 cycles through the event loop. (N.B. The "done callback"
        # is scheduled via call_soon, so it typically takes 2 cycles.)

        assert asyncio.iscoroutine(coro)
        task = self._loop.create_task(coro)
        task.add_done_callback(self._task_done)
        self._tasks.add(task)
        LOGGER.debug('Create task %r', task)
        return task

    def _task_done(self, task):
        """Called when task is finished."""

        LOGGER.debug('Task done %r', task)
        self._tasks.discard(task)

    def cancel(self):
        """Cancel all managed async tasks."""

        for task in self._tasks:
            LOGGER.debug('Cancel task %r', task)
            task.cancel()

    async def wait_cancelled(self):
        """Wait for cancelled tasks to complete."""

        # It takes 2 cycles through the event loop for a task to be cancelled
        # and invoke its done_callback.
        for _ in range(2):
            await asyncio.sleep(0)

        if len(self) > 0:
            raise RuntimeError(
                'TaskSet: Cancelled tasks did not exit as expected')

    def __len__(self):
        """Return length of task list."""

        return len(self._tasks)

    def __contains__(self, task):
        """Return true if task is in set."""

        return task in self._tasks

    def __iter__(self):
        """Return iterable for task set."""

        return iter(self._tasks)
