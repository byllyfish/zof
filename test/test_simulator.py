import unittest
import asyncio
import ofp_app
from ofp_app.controller import Controller


class SimulatorTestCase(unittest.TestCase):
    def test_simulator(self):
        import ofp_app.demo.simulator as sim
        import ofp_app.service.device as _
        from ofp_app.logging import init_logging

        init_logging('INFO')

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app = ofp_app.Application('test_simulator')
        app.count = 0

        @app.event('device_up')
        def device_up(_):
            app.count += 1
            if app.count == sim.app.args.sim_count:
                app.logger.info('all devices up')
                app.post_event('EXIT', exit_status=0)

        @app.event(any)
        def any_event(event):
            app.logger.info(event)

        parser = ofp_app.common_args(under_test=True)
        args = parser.parse_args(['--sim-count=50', '--sim-timeout=3'])
        exit_status = ofp_app.run(args=args)
        self.assertEqual(exit_status, 0)
