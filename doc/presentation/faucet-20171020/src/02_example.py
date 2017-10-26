import zof

APP = zof.Application(__name__)

def role_request(role, generation_id):
    return {
        'type': 'ROLE_REQUEST',
        'msg': {
            'role': role,
            'generation_id': generation_id
        }
    }

@APP.message('CHANNEL_UP')
def channel_up(event):
    ofmsg = role_request('ROLE_MASTER', 1)
    zof.compile(ofmsg).send()

if __name__ == '__main__':
    zof.run()
