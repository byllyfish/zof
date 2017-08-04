"""Implements AsyncTestCase class."""

import asyncio
import inspect
import unittest

# Test timeout in seconds
_TIMEOUT = 10.0


# Method decorator for async tests.
def _wrap_async(func):
    """ Method decorator for async tests. """

    def _wrap(self):
        task = asyncio.wait_for(func(self), _TIMEOUT)
        AsyncTestCase.loop.run_until_complete(task)

    return _wrap


class AsyncTestCase(unittest.TestCase):
    """TestCase subclass that supports `async def` tests.

    Coroutine functions are automatically wrapped in a function that runs them
    using `AsyncTestCase.loop.run_until_complete`.

    To use this class, just create a subclass and write test methods as usual:

        class MyTestCase(AsyncTestCase):

            async def test_foo(self):
                await asyncio.sleep(5)
    """

    @classmethod
    def setUpClass(cls):
        AsyncTestCase.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)
        # Wrap test_ functions and setUp/tearDown if they are coroutine
        # functions.
        for key in dir(cls):
            if key.startswith('test_') or key in ('setUp', 'tearDown'):
                func = getattr(cls, key)
                if inspect.iscoroutinefunction(func):
                    setattr(cls, key, _wrap_async(func))

    @classmethod
    def tearDownClass(cls):
        AsyncTestCase.loop.close()
