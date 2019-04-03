"""Test backport functions."""

import asyncio

from zof.backport import asyncio_run, get_running_loop, current_task


def test_asyncio_run():
    """Test asyncio_run function."""

    task = None

    async def _sleep(secs):
        assert current_task() == task
        await asyncio.sleep(secs)

    async def _main():
        nonlocal task
        loop = get_running_loop()
        task = loop.create_task(_sleep(1))
        await asyncio.sleep(0.1)
        return 34

    result = asyncio_run(_main())
    assert result == 34
    assert task.cancelled()
