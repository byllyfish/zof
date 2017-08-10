import unittest
import asyncio
import zof
from zof.controller import Controller


class SimulatorTester(zof.Application):
    def __init__(self, sim_app):
        super().__init__('test_simulator')
        self.count = 0
        self.sim_app = sim_app

        # Register instance methods by applying decorators.
        self.message('channel_up')(self.channel_up)
        self.message('channel_down')(self.channel_down)
        self.message('features_reply')(self.features_reply)
        self.message(any)(self.other_message)

    def channel_up(self, event):
        self.logger.info('channel_up')
        self.count += 1
        if self.count == self.sim_app.args.sim_count:
            self.logger.info('all channels up')
            zof.post_event('EXIT', exit_status=0)

    def channel_down(self, event):
        self.logger.info('channel_down')

    def features_reply(self, event):
        pass

    def other_message(self, event):
        self.logger.info(event)



class SimulatorTestCase(unittest.TestCase):

    def test_simulator(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from zof.demo.simulator import APP as sim
        from zof.service.datapath import APP as dpa
        tester = SimulatorTester(sim)

        zof.set_apps([dpa, sim, tester])
        parser = zof.common_args(under_test=True)
        args = parser.parse_args(['--sim-count=50', '--sim-timeout=5'])
        exit_status = zof.run(args=args)
        self.assertEqual(exit_status, 0)
