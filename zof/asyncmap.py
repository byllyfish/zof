import asyncio
import sys

_PY36 = sys.version_info[0:2] >= (3, 6)

if _PY36:
    from .asyncmap36 import asyncmap  # pylint: disable=unused-import

else:

    class asyncmap:  # pylint: disable=invalid-name
        """
        Async generator object that is a port of the asyncmap36 generator.

        This is needed for Python 3.5 which doesn't support "yield inside a coroutine".
        """

        def __init__(self,
                     coro,
                     seq,
                     *,
                     ensure_future=asyncio.ensure_future,
                     parallelism=1):
            assert seq
            self.coro = coro
            self.seq = seq
            self.ensure_future = ensure_future
            self.pending = [
                ensure_future(coro(param)) for param in seq[0:parallelism]
            ]
            self.done = set()
            self.next_idx = parallelism

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.done:
                return self.done.pop()
            if not self.pending:
                raise StopAsyncIteration
            self.done, self.pending = await asyncio.wait(
                self.pending, return_when=asyncio.FIRST_COMPLETED)
            for _ in self.done:
                if self.next_idx < len(self.seq):
                    self.pending.add(
                        self.ensure_future(self.coro(self.seq[self.next_idx])))
                    self.next_idx += 1
            return self.done.pop()
