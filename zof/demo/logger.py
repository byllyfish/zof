import asyncio
import zof

APP = zof.Application('logger', precedence=0)

APP.logger.info('phase = %r', APP.phase)


@APP.event('PREFLIGHT')
def preflight(event):
    APP.logger.info('event = %r', event)


@APP.event('POSTFLIGHT')
def postflight(event):
    APP.logger.info('event = %r', event)


@APP.event('SIGNAL')
def signal(event):
    APP.logger.info('event = %r', event)


@APP.event('PRESTART')
async def prestart(event):
    await logger(event)


@APP.event('START')
async def start(event):
    await logger(event)


@APP.event('STOP')
async def stop(event):
    await logger(event)


@APP.message(any)
@APP.event(any)
def other(event):
    APP.logger.warning('event = %r', event)


async def logger(event):
    try:
        APP.logger.info('async event = %r', event)
        await asyncio.sleep(3)
    except asyncio.CancelledError:
        APP.logger.warning('async event cancelled = %r', event)
    finally:
        APP.logger.info('async event done = %r', event)


if __name__ == '__main__':
    zof.run()
