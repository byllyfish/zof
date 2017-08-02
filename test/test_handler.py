import unittest
from zof.handler import make_handler
from zof.objectview import make_objectview
from zof.event import make_event

NO_HELP = 'No help available'


class HandlerTestCase(unittest.TestCase):
    def test_func(self):
        h = make_handler(func, 'message', 'FEATURES_REQUEST')
        self.assertTrue(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)
        self.assertEqual('Brief line.', h.help_brief())
        self.assertEqual('Brief line.\n\nThis is a test func.', h.help())

        h = make_handler(func_nodoc, 'message', 'ECHO_REQUEST')
        self.assertTrue(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual('ECHO_REQUEST', h.subtype)
        self.assertEqual(NO_HELP, h.help_brief())
        self.assertEqual(NO_HELP, h.help())

    def test_async_func(self):
        h = make_handler(async_func, 'message', 'FEATURES_REQUEST')
        self.assertTrue(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)
        self.assertEqual('Async func.', h.help_brief())
        self.assertEqual('Async func.\n\nThis is an async func.', h.help())

    def test_bad_func(self):
        h = make_handler(bad_func, 'message', 'FEATURES_REQUEST')
        self.assertFalse(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)
        self.assertEqual(NO_HELP, h.help_brief())
        self.assertEqual(NO_HELP, h.help())

    def test_any_subtype(self):
        h = make_handler(func, 'message', any)
        self.assertTrue(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual(any, h.subtype)
        self.assertEqual('Brief line.', h.help_brief())
        self.assertEqual('Brief line.\n\nThis is a test func.', h.help())

    def test_bad_subtype_function(self):
        h = make_handler(func, 'message', bad_func)
        self.assertFalse(h.verify())

    def test_message_filter(self):
        h1 = make_handler(func, 'message', 'PACKET_IN', {'cookie': 123})
        self.assertTrue(h1.verify())

        h2 = make_handler(func, 'message', 'PACKET_IN', {'x': 9})
        self.assertTrue(h2.verify())

        evt = make_objectview({
            'datapath_id': '00:00:00:00:00:00:00:01',
            'type': 'PACKET_IN',
            'msg': {
                'cookie': 124
            }
        })
        self.assertFalse(h1.match(evt))
        self.assertFalse(h2.match(evt))
        evt.msg.cookie = 123
        self.assertTrue(h1.match(evt))
        self.assertFalse(h2.match(evt))
        evt.type = 'PACKET_OUT'
        self.assertFalse(h1.match(evt))
        self.assertFalse(h2.match(evt))

    def test_message_datapath(self):
        # Test datapath_id=None filter on message handler.
        h = make_handler(func, 'message', 'PACKET_OUT', {})
        self.assertTrue(h.verify())

        evt = make_objectview({
            'datapath_id': '00:00:00:00:00:00:00:01',
            'type': 'PACKET_OUT',
            'msg': {
                'cookie': 124
            }
        })
        self.assertTrue(h.match(evt))
        evt.datapath_id = None
        self.assertTrue(h.match(evt))
        del evt['datapath_id']
        self.assertFalse(h.match(evt))  # only case where it makes a difference

    def test_message_no_datapath(self):
        # Test datapath_id=None filter on message handler.
        h = make_handler(func, 'message', 'PACKET_OUT', {'datapath_id': None})
        self.assertTrue(h.verify())

        evt = make_objectview({
            'datapath_id': '00:00:00:00:00:00:00:01',
            'type': 'PACKET_OUT',
            'msg': {
                'cookie': 124
            }
        })
        self.assertFalse(h.match(evt))
        evt.datapath_id = None
        self.assertFalse(h.match(evt))
        del evt['datapath_id']
        self.assertTrue(h.match(evt))

    def test_event_filter(self):
        h1 = make_handler(func, 'event', 'SIGNAL', {'signal': 'SIGHUP'})
        self.assertTrue(h1.verify())

        h2 = make_handler(func, 'event', 'SIGNAL', {'x': 3})
        self.assertTrue(h2.verify())

        evt = make_event(event='SIGNAL', signal='SIGTERM')
        self.assertFalse(h1.match(evt))
        self.assertFalse(h2.match(evt))
        evt.signal = 'SIGHUP'
        self.assertTrue(h1.match(evt))
        self.assertFalse(h2.match(evt))


def func(event):
    """
    Brief line.

    This is a test func.
    """
    pass


def func_nodoc(event):
    pass


async def async_func(event):
    """Async func.

    This is an async func.
    """
    pass


def bad_func():
    # Func doesn't have __doc__.
    pass
