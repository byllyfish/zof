import pytest
import asyncio
from zoflite.taskset import TaskSet


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio

async def _mock_task():
	await asyncio.sleep(5)


async def test_taskset_container(event_loop):
	"""Test basic container functionality."""

	tasks = TaskSet(event_loop)
	task = tasks.create_task(_mock_task)

	assert tasks
	assert len(tasks) == 1
	assert task in tasks
	assert list(tasks) == [task]

	tasks.cancel()
	for _ in range(2):
		await asyncio.sleep(0)

	assert not tasks
	assert len(tasks) == 0
	assert task not in tasks
	assert list(tasks) == []


async def test_taskset_cancel(event_loop):
	"""Test task cancellation."""

	tasks = TaskSet(event_loop)
	task = tasks.create_task(_mock_task())
	assert len(tasks) == 1

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


async def test_taskset_cancel_nostart(event_loop):
	"""Test task cancellation when task never gets time to start."""

	tasks = TaskSet(event_loop)	
	task = tasks.create_task(_mock_task())

	# Cancel the task that hasn't started yet.
	tasks.cancel()

	# Task removed after 2 cycles through the event loop.
	for _ in range(2):
		assert len(tasks) <= 1
		await asyncio.sleep(0)

	assert len(tasks) == 0
