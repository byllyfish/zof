import unittest
import asyncio
from ofp_app.controller import Controller
from ofp_app import Application


class SimulatorTestCase(unittest.TestCase):

    def test_simulator(self):
        import  ofp_app.demo.simulator as sim
        import ofp_app.service.device as dev
        from ofp_app.logging import init_logging

        init_logging('INFO')
        sim.app.simulator_count = 50

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _exit_timeout():
            try:
                await asyncio.sleep(3.0)
                self.assertEqual(sim.app.simulator_count, len(dev.app.devices))
            finally:
                sim.app.post_event('EXIT')
        
        task = asyncio.ensure_future(_exit_timeout())

        app = Application('test_simulator')
        app.count = 0

        @app.event('device_up')
        def device_up(_):
            app.count += 1
            if app.count == sim.app.simulator_count:
                app.logger.info('all devices up')
                app.post_event('EXIT')

        @app.event(any)
        def any_event(event):
            app.logger.info(event)

        controller = Controller.singleton()
        controller.run_loop(listen_endpoints=[6653])
        Controller.destroy()

        ex = task.exception()
        if ex:
            raise ex

