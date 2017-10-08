import time
import zof
from zof.controller import Controller

APP = zof.Application('oftr_bench')
CONTROLLER = Controller.singleton()
N = 10000


@APP.event('start')
async def start(event):
    for i in range(5):
        start_time = time.time()
        for _ in range(N):
            await CONTROLLER.rpc_call('OFP.DESCRIPTION')
        end_time = time.time()
        elapsed = end_time - start_time
        print('Elapsed %r/%r' % (elapsed, elapsed / N))
    zof.post_event('EXIT')


if __name__ == '__main__':
    zof.run()
