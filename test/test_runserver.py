import unittest
import asyncio
import signal
from zof.run_server import run_server


class RunServerTestCase(unittest.TestCase):
    def test_stopping_task(self):
        """Verify with task that calls stop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _task():
            asyncio.get_event_loop().stop()

        asyncio.ensure_future(_task())
        run_server()
        self.assert_final_task_count(0)

    def test_empty_task(self):
        """Verify with task that immediately returns.

        `run_server` will continue running even when there are no tasks
        scheduled at all. Use an alarm signal to force the test to finish.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _task():
            pass

        asyncio.ensure_future(_task())
        signal.alarm(1)
        run_server(signals=['SIGALRM'])
        self.assert_final_task_count(0)

    def test_destroyed_task_pending(self):
        """Verify with task that sleeps in an infinite loop calling stop.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _task():
            while True:
                await asyncio.sleep(0.1)
                asyncio.get_event_loop().stop()

        task = asyncio.ensure_future(_task())
        run_server(pending_timeout=0.001)
        self.assertTrue(loop.is_closed())

        tasks = asyncio.Task.all_tasks(loop)
        self.assertEqual({task}, tasks)
        with self.assertRaisesRegex(RuntimeError, 'Event loop is closed'):
            # This call may cause a 'Task was destroyed but it is pending!'
            # message. This is okay, but let's try to disable the log message.
            task._log_destroy_pending = False
            task.cancel()

    def assert_final_task_count(self, n):
        """Verify that event loop is closed and there are `n` tasks pending.
        """
        loop = asyncio.get_event_loop()
        self.assertTrue(loop.is_closed())
        self.assertEqual(n, len(asyncio.Task.all_tasks(loop)))
