# tfm_request.py

import zof


class TfmRequest:
    """Demo app that issues a TableFeatures request."""

    async def on_channel_up(self, dp, _event):
        ofmsg = {'type': 'TABLE_FEATURES_REQUEST'}
        reply = await dp.request(ofmsg)
        tables = [table['name'] for table in reply['msg']]
        print(tables)


if __name__ == '__main__':
    zof.run(TfmRequest())
