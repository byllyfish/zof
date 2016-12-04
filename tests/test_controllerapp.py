import unittest
import os
from pylibofp.controllerapp import ControllerApp
from pylibofp.appfacade import AppFacade


class MockController(object):
    def __init__(self):
        self.shared = None
        self.config = None
        self.datapaths = None
        self.apps = []


class ControllerAppTestCase(unittest.TestCase):

    def setUp(self):
        app = ControllerApp(MockController(), name='mock-app')
        ofp = AppFacade(app)

        @ofp.channel('all')
        def _channel_default(event):
            ofp.shared['handler'] = 'channel_default'

        @ofp.message('all')
        def _message_default(event):
            ofp.shared['handler'] = 'message_default'

        @ofp.event('all')
        def _event_default(event):
            ofp.shared['handler'] = 'event_default'

        self.handlers = app._handlers

    def test_handlers(self):
        """Test that all handlers are loaded."""
        
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
