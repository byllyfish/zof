import unittest
from ofp_app.controllerapp import ControllerApp
from ofp_app.appref import AppRef


class MockController(object):
    def __init__(self):
        self.apps = []


class ControllerAppTestCase(unittest.TestCase):

    def setUp(self):
        app = ControllerApp(MockController(), name='mock-app')
        ofp = AppRef(app)

        @ofp.message(any)
        def _message_default(event):
            pass

        @ofp.event(any)
        def _event_default(event):
            pass

        # For testing "stacking" of decorators.
        @ofp.message('CHANNEL_DOWN')
        @ofp.event('START')
        @ofp.message('CHANNEL_ALERT')
        @ofp.event('STOP')
        @ofp.message('CHANNEL_UP')
        def _multiple(event):
            pass

        self.handlers = app.handlers

    def test_handlers(self):
        """Test that all handlers are loaded."""
        
        self.assertEqual(2, len(self.handlers))
        self.assertEqual(4, len(self.handlers['message']))
        self.assertEqual(3, len(self.handlers['event']))
        
        message = self.handlers['message'][0]
        event = self.handlers['event'][0]

        self.assertEqual('message', message.type)
        self.assertEqual(any, message.subtype)
        self.assertEqual({}, message.options)

        self.assertEqual('event', event.type)
        self.assertEqual(any, event.subtype)
        self.assertEqual({}, event.options)
