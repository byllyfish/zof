import asyncio
from zoflite.backport import asyncio_run


def test_asyncio_run():
    """Test asyncio_run backported function."""

    async def test():
        await asyncio.sleep(0)
        return 5

    result = asyncio_run(test())
    assert result == 5
