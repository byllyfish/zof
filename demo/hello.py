import asyncio
import zof


class HelloWorld:

    def on_channel_up(self, dp, event):
        print(dp, event)

    def on_channel_down(self, dp, event):
        print(dp, event)


asyncio.run(zof.run_controller(HelloWorld()))
