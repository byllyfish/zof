import asyncio
import zof


class HelloWorld(zof.Controller):

    def on_channel_up(self, dp, event):
        print(dp, event)

    def on_channel_down(self, dp, event):
        print(dp, event)


controller = HelloWorld()
asyncio.run(controller.run())
