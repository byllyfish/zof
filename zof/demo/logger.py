import asyncio
import zof

APP = zof.Application('logger', precedence=0)

APP.logger.info('phase = %r', APP.phase)


@APP.event('POSTSTOP')
def poststop(event):
    APP.logger.info('event = %r', event)


@APP.event('STOP')
async def stop(event):
    await logger(event)


@APP.message(any)
@APP.event(any)
async def logger(event):
    try:
        APP.logger.info('event = %r', event)
        await asyncio.sleep(3)
    except asyncio.CancelledError:
        APP.logger.warning('event cancelled = %r', event)
    finally:
        APP.logger.info('event done = %r', event)


if __name__ == '__main__':
    zof.run()
