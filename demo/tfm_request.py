# tfm_request.py

import asyncio
import zof


class TfmRequest(zof.Controller):
    """Demo app that issues a TableFeatures request."""

    async def on_channel_up(self, dp, _event):
        ofmsg = {'type': 'REQUEST.TABLE_FEATURES'}
        reply = await dp.request(ofmsg)
        tables = [table['name'] for table in reply['msg']]
        print(tables)


if __name__ == '__main__':
    asyncio.run(TfmRequest().run())  # type: ignore
