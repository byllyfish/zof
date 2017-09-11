import asyncio


async def asyncmap(coro,
                   seq,
                   *,
                   ensure_future=asyncio.ensure_future,
                   parallelism=1):
    """
    Returns a coroutine object that, when awaited, yields the next result.

    This function lets you specify the amount of parallelism.

        async def request(target):
            ...

        targets = [1, 2, 3, 4, 5]

        async for next_result in async_map(request, targets, parallelism=2):
            try:
                # You MUST await the result even though it is done.
                assert next_result.done()
                result = await next_result
                ...
            except Exception:
                pass
    """

    assert seq
    pending = [ensure_future(coro(param)) for param in seq[0:parallelism]]
    next_idx = parallelism

    while pending:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED)
        for fut in done:
            if next_idx < len(seq):
                pending.add(ensure_future(coro(seq[next_idx])))
                next_idx += 1
            yield fut
