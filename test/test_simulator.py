import unittest
import asyncio
import zof


class SimulatorTestCase(unittest.TestCase):
    def test_simulator(self):
        import zof.demo.simulator as sim
        import zof.service.device as _
        from zof.logging import init_logging

        init_logging('INFO')

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app = zof.Application('test_simulator')
        app.count = 0

        @app.event('device_up')
        def device_up(_):
            app.count += 1
            if app.count == sim.app.args.sim_count:
                app.logger.info('all devices up')
                app.post_event('EXIT', exit_status=0)

        @app.event('device_down')
        def device_down(_):
            pass

        @app.event(any)
        def any_event(event):
            app.logger.info(event)

        parser = zof.common_args(under_test=True)
        args = parser.parse_args(['--sim-count=50', '--sim-timeout=3'])
        exit_status = zof.run(args=args)
        self.assertEqual(exit_status, 0)
