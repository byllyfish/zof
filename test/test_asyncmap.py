from .asynctestcase import AsyncTestCase
import asyncio
from zof.asyncmap import asyncmap


class AsyncMapTestCase(AsyncTestCase):
    async def test_asyncmap(self):
        parallel = 0
        max_parallel = 0

        async def _test(target):
            nonlocal parallel, max_parallel
            try:
                parallel += 1
                if parallel > max_parallel:
                    max_parallel = parallel
                await asyncio.sleep(0.05)
                if target == 3:
                    raise ValueError(target)
                return target
            finally:
                parallel -= 1

        targets = [1, 2, 3, 4, 5]
        for parallelism in (1, 2, 3, 4, 5, 6, 8):
            output = set()
            max_parallel = 0
            async for next_result in asyncmap(
                    _test, targets, parallelism=parallelism):
                try:
                    assert next_result.done()
                    result = await next_result
                    output.add('+%s' % result)
                except ValueError as ex:
                    output.add('x%s' % ex)
            self.assertEqual(output, {'+2', '+1', 'x3', '+5', '+4'})
            self.assertEqual(max_parallel, min(parallelism, len(targets)))
