
import asyncio
import signal
import zof


class HelloSignal(zof.Controller):
    def on_start(self):
        asyncio.get_event_loop().add_signal_handler(signal.SIGHUP, self.handle_sighup)

    def on_stop(self):
        asyncio.get_event_loop().remove_signal_handler(signal.SIGHUP)

    def handle_sighup(self):
        print('SIGHUP')


if __name__ == '__main__':
    asyncio.run(HelloSignal().run())
