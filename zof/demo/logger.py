import asyncio
import zof

app = zof.Application('logger', precedence=0)

app.logger.info('phase = %r', app.phase)


@app.event('POSTSTOP')
def poststop(event):
    app.logger.info('event = %r', event)


@app.event('STOP')
async def stop(event):
    await logger(event)


@app.message(any)
@app.event(any)
async def logger(event):
    try:
        app.logger.info('event = %r', event)
        await asyncio.sleep(3)
    except asyncio.CancelledError:
        app.logger.warning('event cancelled = %r', event)
    finally:
        app.logger.info('event done = %r', event)


if __name__ == '__main__':
    zof.run()
