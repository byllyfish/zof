import unittest
import os
from pylibofp.controllerapp import ControllerApp


MOCK_APP = '%s/mock_module.py' % os.path.dirname(__file__)


class MockController(object):
    def __init__(self):
        self.shared = None
        self.config = None
        self.datapaths = None

class ControllerAppTestCase(unittest.TestCase):

    def setUp(self):
        app = ControllerApp(MockController(), MOCK_APP)
        self.handlers = app._handlers

    def test_handlers(self):
        "Test that all handlers are loaded."
        
        self.assertEqual(3, len(self.handlers))
        self.assertEqual(1, len(self.handlers['channel']))
        self.assertEqual(1, len(self.handlers['message']))
        self.assertEqual(1, len(self.handlers['event']))
        
        channel = self.handlers['channel'][0]
        message = self.handlers['message'][0]
        event = self.handlers['event'][0]

        self.assertEqual('channel', channel.type)
        self.assertEqual('ALL', channel.subtype)
        self.assertEqual({}, channel.options)

        self.assertEqual('message', message.type)
        self.assertEqual('ALL', message.subtype)
        self.assertEqual({}, message.options)

        self.assertEqual('event', event.type)
        self.assertEqual('ALL', event.subtype)
        self.assertEqual({}, event.options)
