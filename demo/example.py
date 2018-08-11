import asyncio
import zof


class MyController(zof.Controller):
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


if __name__ == '__main__':
    asyncio.run(MyController().run())  # type: ignore
