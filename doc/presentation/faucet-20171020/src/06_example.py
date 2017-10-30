import zof

APP = zof.Application(__name__)

TABLE_FEATURES = zof.compile('''
  type: REQUEST.TABLE_FEATURES
  msg: []
''')

@APP.message('CHANNEL_UP')
async def channel_up(event):
    entry_count = 0
    async for reply in TABLE_FEATURES.request():
        entry_count += len(reply['msg'])
    print("TableFeatures: %d entries received" % entry_count)

if __name__ == '__main__':
    zof.run()
