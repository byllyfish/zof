import zof
import asyncio

APP = zof.Application(__name__)

PORT_STATS = zof.compile('''
  type: REQUEST.PORT_STATS
  msg:
    port_no: $port
''')

@APP.message('CHANNEL_UP')
async def channel_up(event):
    while True:
        reply = await PORT_STATS.request(port='ANY')
        for stats in reply['msg']:
            print(stats)
        await asyncio.sleep(5)

if __name__ == '__main__':
    zof.run()
