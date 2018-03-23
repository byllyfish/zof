import pytest
import asyncio
from functools import wraps
from zoflite.dispatcher import Dispatcher


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio


async def test_ordering():
	"""Dispatcher should dispatch events in deterministic order."""

	class Test:
		def __init__(self):
			self.events = []

		def ev0(self, event):
			self.events.append(event['xid'])

		async def ev1(self, event):
			self.events.append(event['xid'])
			await asyncio.sleep(0)
			self.events.append(100 + event['xid'])

	test = Test()
	dispatcher = Dispatcher(test)

	# The dispatcher schedules the callbacks.
	for i in range(10):
		event = { 'type': 'EV%d' % (i % 2), 'xid': i }
		dispatcher(event)
	
	# Callbacks are not called until current task yields.
	assert test.events == []
	await asyncio.sleep(0)
	assert test.events == list(range(10))

	# Check second part of async callback.
	test.events = []
	await asyncio.sleep(0)
	assert test.events == [101, 103, 105, 107, 109]


def _catch(exc_class, callback):
    """Invoke callback on unhandled exception"""

    def _koe(func):
        @wraps(func)
        def __koe(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except exc_class as ex:
                callback(ex)

        @wraps(func)
        async def __akoe(*args, **kwargs):
            try:
                await func(*args, **kwargs)
            except asyncio.CancelledError:
                pass
            except exc_class as ex:
                callback(ex)

        return __akoe if asyncio.iscoroutinefunction(func) else __koe

    return _koe


async def test_exception_caught(caplog):
	"""Exceptions in callbacks are visible only if caught explicitly."""

	exlist = []

	def exc_callback(ex):
		exlist.append(ex)

	class Test:
		@_catch(Exception, exc_callback)
		def ev0(self, event):
			raise Exception('fail 0')

		@_catch(Exception, exc_callback)
		async def ev1(self, event):
			raise Exception('fail 1')

	test = Test()
	dispatcher = Dispatcher(test)

	# The dispatcher schedules the callbacks.
	for i in range(2):
		event = { 'type': 'EV%d' % (i % 2), 'xid': i }
		dispatcher(event)

	assert exlist == []
	await asyncio.sleep(0)
	assert [str(ex) for ex in exlist] == ['fail 0', 'fail 1']
	assert not caplog.record_tuples


async def test_exception_handler(caplog):
	"""Exceptions in callbacks can be caught with set_exception_handler."""

	exlist = []

	def _exception_handler(_loop, context):
		exlist.append(context['exception'])

	class Test:
		def ev0(self, event):
			raise ValueError('fail 0')

		async def ev1(self, event):
			raise ValueError('fail 1')

	asyncio.get_event_loop().set_exception_handler(_exception_handler)

	test = Test()
	dispatcher = Dispatcher(test)

	# The dispatcher schedules the callbacks.
	for i in range(2):
		event = { 'type': 'EV%d' % (i % 2)}
		dispatcher(event)

	# ValueError is raised when event is actually dispatched.
	assert exlist == []
	await asyncio.sleep(0)
	assert [str(ex) for ex in exlist] == ['fail 0', 'fail 1']
	
	assert not caplog.record_tuples


async def test_events_not_modified():
	"""Dispatched events should not be modified/copied."""

	class Test:
		def __init__(self):
			self.events = []

		def ev0(self, event):
			self.events.append(event)

		async def ev1(self, event):
			self.events.append(event)

	test = Test()
	dispatcher = Dispatcher(test)

	# Construct events.
	events = [{ 'type': 'EV%d' % (i % 2), 'xid': i } for i in range(10)]

	# The dispatcher schedules the callbacks.
	for event in events:
		dispatcher(event)
	
	# Callbacks are not called until current task yields.
	assert test.events == []
	await asyncio.sleep(0)

	# Events are identical; both in content and identity.
	assert test.events == events
	for i in range(len(events)):
		assert events[i] is test.events[i]


async def test_dispatch_other():
	"""Dispatcher should dispatch unrecognized events to 'other' handler."""

	class Test:
		def __init__(self):
			self.other_events = []

		def other(self, event):
			self.other_events.append(event['xid'])

	test = Test()
	dispatcher = Dispatcher(test)

	# The dispatcher schedules the callbacks.
	for i in range(10):
		event = { 'type': 'EV%d' % (i % 2), 'xid': i }
		dispatcher(event)
	
	# Callbacks are not called until current task yields.
	assert test.other_events == []
	await asyncio.sleep(0)
	assert test.other_events == list(range(10))
