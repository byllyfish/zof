import logging
import asyncio

LOGGER = logging.getLogger('__package__')


class Dispatcher:
	"""Dispatch events to instance methods of object instance(s)."""

	def __init__(self, *instances):
		self._instances = instances
		self._loop = asyncio.get_event_loop()
		self._stopped = self._loop.create_future()

	def __call__(self, event):
		"""Dispatch event to all instances."""
		
		event_type = event['type'].lower()

		# Check for 'stop' event.
		if event_type == 'stop':
			self._stop()
			return

		# For each instance, find the method matching the event_type
		# and invoke it. If there's no such method but a method named
		# 'other' exists, call the 'other' method.
		for instance in self._instances:
			callback = getattr(instance, event_type, None)
			if not callback:
				# Look for 'other' handler.
				callback = getattr(instance, 'other', None)
				if not callback:
					continue
			# Invoke callback function appropriately (async or not).
			if asyncio.iscoroutinefunction(callback):
				self._loop.create_task(callback(event))
			else:
				# Instead of calling the function directly, have it called
				# ASAP by the event loop. The intent is that event dispatch
				# remains in FIFO order whether it's async or not.
				self._loop.call_soon(callback, event)

	async def run(self):
		"""Run until we receive a 'stop' event."""

		self.__call__({'type': 'start'})
		await self._stopped # and remaining tasks have completed...

	def _stop(self):
		self._stopped.set_result(0)
		# TODO(bfish): Call stop handlers?