import pytest
import asyncio
from zoflite.tasklist import TaskList


async def _mock_task():
    await asyncio.sleep(5)


@pytest.mark.asyncio
async def test_tasklist_container(event_loop):
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
