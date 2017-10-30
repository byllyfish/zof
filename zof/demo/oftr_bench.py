from timeit import default_timer as timer
import zof
from zof.controller import Controller

APP = zof.Application('oftr_bench')
CONTROLLER = Controller.singleton()
N = 10000


@APP.event('start')
async def start(event):
    for i in range(5):
        start_time = timer()
        for _ in range(N):
            await CONTROLLER.rpc_call('OFP.DESCRIPTION')
        end_time = timer()
        elapsed = end_time - start_time
        APP.logger.info('Elapsed %r', elapsed)
    zof.post_event({'event': 'EXIT'})


if __name__ == '__main__':
    zof.run()
