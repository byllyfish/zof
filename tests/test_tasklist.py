import pytest
import asyncio
from zoflite.tasklist import TaskList


async def _mock_task():
    await asyncio.sleep(5)


@pytest.mark.asyncio
async def test_tasklist_container(event_loop, caplog):
    """Test basic container functionality."""

    tasks = TaskList(event_loop)
    task = tasks.create_task(_mock_task())

    assert tasks
    assert len(tasks) == 1
    assert task in tasks
    assert list(tasks) == [task]

    tasks.cancel()

    assert len(tasks) == 1
    assert list(tasks) == [task]

    # Wait for task to be removed.
    await tasks.wait_cancelled()

    assert not tasks
    assert len(tasks) == 0
    assert task not in tasks
    assert list(tasks) == []

    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_tasklist_cancel(event_loop):
    """Test task cancellation."""

    tasks = TaskList(event_loop)
    task = tasks.create_task(_mock_task())
    assert len(tasks) == 1
    assert list(tasks)[0] is task

    # Give task time to start.
    await asyncio.sleep(0)
    assert len(tasks) == 1

    # Cancel the task.
    tasks.cancel()

    # Task removed after 2 cycles through the event loop.
    for _ in range(2):
        assert len(tasks) <= 1
        await asyncio.sleep(0)

    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_tasklist_cancel_nostart(event_loop):
    """Test task cancellation when task never gets time to start."""

    tasks = TaskList(event_loop)
    tasks.create_task(_mock_task())

    # Cancel the task that hasn't started yet.
    tasks.cancel()

    # Task removed after 2 cycles through the event loop.
    for _ in range(2):
        assert len(tasks) <= 1
        await asyncio.sleep(0)

    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_tasklist_wait_cancelled(event_loop):
    """Test wait_cancelled() raises an error when tasks don't cancel."""

    async def _uncancellable():
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            await asyncio.sleep(1)

    tasks = TaskList(event_loop)
    task = tasks.create_task(_uncancellable())

    await asyncio.sleep(0)
    assert len(tasks) == 1

    tasks.cancel()

    with pytest.raises(RuntimeError):
        # Task doesn't exit immediately.
        await tasks.wait_cancelled()

    assert len(tasks) == 1
    await task


@pytest.mark.asyncio
async def test_tasklist_return_value(event_loop):
    """Test task returned from create_task can be awaited."""

    async def _my_task():
        return 123

    tasks = TaskList(event_loop)
    task = tasks.create_task(_my_task())

    result = await task
    assert result == 123


@pytest.mark.asyncio
async def test_tasklist_exception(event_loop, caplog):
    """Test task raises an exception."""

    excs = []

    def _on_exception(exc):
        excs.append(exc)

    # Test that loop's exception handler is NOT called.
    def _exc_handler(_loop, context):
        excs.append(context)

    event_loop.set_exception_handler(_exc_handler)

    async def _my_task():
        raise RuntimeError('invalid')

    tasks = TaskList(event_loop, _on_exception)
    task = tasks.create_task(_my_task())

    # This task we retain and await.
    with pytest.raises(RuntimeError) as excinfo:
        await task

    assert len(excs) == 1
    assert str(excinfo.value) == 'invalid'
    assert excinfo.value is excs[0]

    # This task is not retained or awaited...
    excs.clear()
    tasks.create_task(_my_task())
    await tasks.wait_cancelled()

    assert len(excs) == 1
    assert str(excs[0]) == 'invalid'

    assert not caplog.record_tuples
