import asyncio
from zoflite.driver import Driver
from zoflite.backport import asyncio_run


class MyController:

    def __init__(self):
        self.driver = Driver(self._dispatch)

    async def run(self):
        async with self.driver:
            await self.driver.listen('6653', options=['FEATURES_REQ'])
            await asyncio.sleep(30)

    def _dispatch(self, _driver, event):
        msg_type = event['type'].replace('.', '_')
        msg_method = getattr(self, msg_type, None)
        if msg_method:
            msg_method(event)
        else:
            print('other: %r' % event)

    def CHANNEL_UP(self, event):
        asyncio.ensure_future(self._request_desc(event['conn_id']))

    async def _request_desc(self, conn_id):
        ofmsg = {
            'conn_id': conn_id,
            'type': 'REQUEST.DESC'
        }
        desc = await self.driver.request(ofmsg)
        print('_request_desc %r' % desc)        



if __name__ == '__main__':
    asyncio_run(MyController().run())
