import zof

APP = zof.Application(__name__)

ROLE_REQUEST = zof.compile('''
  type: ROLE_REQUEST
  msg:
    role: $role
    generation_id: $generation_id
''')

@APP.message('CHANNEL_UP')
async def channel_up(event):
    reply = await ROLE_REQUEST.send(role='ROLE_MASTER', generation_id=1)
    print(reply)

if __name__ == '__main__':
    zof.run()
