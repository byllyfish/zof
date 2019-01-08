import asyncio
import zof


class HelloWorld:

    def on_channel_up(self, dp, event):
        print(dp, event)

    def on_channel_down(self, dp, event):
        print(dp, event)


controller = zof.Controller(HelloWorld())
asyncio.run(controller.run())
