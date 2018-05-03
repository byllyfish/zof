"""Implements a set of async tasks."""

import asyncio


class TaskSet:
    """Manages a collection of async tasks that can be cancelled."""

    def __init__(self, loop):
        self._loop = loop
        self._tasks = set()

    def create_task(self, coro):
        """Create a managed async task."""

        # When a task is cancelled, it should be removed from `self._tasks`
        # within 1-2 cycles through the event loop. (N.B. The done_callback
        # is scheduled via call_soon, so it typically takes 2 cycles.)

        task = self._loop.create_task(coro)
        task.add_done_callback(self._done_callback)
        self._tasks.add(task)
        return task

    def _done_callback(self, task):
        """Called when task is finished."""

        self._tasks.discard(task)

    def cancel(self):
        """Cancel all managed async tasks."""

        for task in self._tasks:
            task.cancel()

    def __len__(self):
        """Return length of task list."""

        return len(self._tasks)

    def __contains__(self, task):
        """Return true if task is in set."""

        return task in self._tasks

    def __iter__(self):
        """Return iterable for task set."""

        return iter(self._tasks)
