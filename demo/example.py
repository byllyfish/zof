import asyncio
from zoflite.controller import Controller

class MyController(Controller):

	async def CHANNEL_UP(self, dp, event):
		try:
			print(dp, event)
			await asyncio.sleep(5)
			print('done')
		except asyncio.CancelledError:
			print('cancelled')

	def CHANNEL_DOWN(self, dp, event):
		print(dp, event)

	def PACKET_IN(self, dp, event):
		print(dp, event)

	async def PORT_STATUS(self, dp, event):
		print(dp, event)


# Invoke your controller's run() coroutine in an event loop.
asyncio.get_event_loop().run_until_complete(MyController().run())
