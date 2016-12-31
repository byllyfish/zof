import unittest
from pylibofp.controllerapp import ControllerApp
from pylibofp.appfacade import AppFacade


class MockController(object):
    def __init__(self):
        self.apps = []


class ControllerAppTestCase(unittest.TestCase):

    def setUp(self):
        app = ControllerApp(MockController(), name='mock-app')
        ofp = AppFacade(app)

        @ofp.message('all')
        def _message_default(event):
            pass

        @ofp.event('all')
        def _event_default(event):
            pass

        self.handlers = app.handlers

    def test_handlers(self):
        """Test that all handlers are loaded."""
        
        self.assertEqual(2, len(self.handlers))
        self.assertEqual(1, len(self.handlers['message']))
        self.assertEqual(1, len(self.handlers['event']))
        
        message = self.handlers['message'][0]
        event = self.handlers['event'][0]

        self.assertEqual('message', message.type)
        self.assertEqual('ALL', message.subtype)
        self.assertEqual({}, message.options)

        self.assertEqual('event', event.type)
        self.assertEqual('ALL', event.subtype)
        self.assertEqual({}, event.options)
