import unittest
from zof.handler import make_handler

NO_HELP = 'No help available'


class HandlerTestCase(unittest.TestCase):
    def test_func(self):
        h = make_handler(func, 'message', 'FEATURES_REQUEST')
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)

        h = make_handler(func_nodoc, 'message', 'ECHO_REQUEST')
        self.assertEqual('message', h.type)
        self.assertEqual('ECHO_REQUEST', h.subtype)

    def test_async_func(self):
        h = make_handler(async_func, 'message', 'FEATURES_REQUEST')
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)

    def test_bad_func(self):
        h = make_handler(bad_func, 'message', 'FEATURES_REQUEST')
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)

    def test_any_subtype(self):
        h = make_handler(func, 'message', any)
        self.assertEqual('message', h.type)
        self.assertEqual(any, h.subtype)

    def test_bad_subtype_function(self):
        h = make_handler(func, 'message', bad_func)

    def test_message_filter(self):
        h1 = make_handler(func, 'message', 'PACKET_IN', {'cookie': 123})

        h2 = make_handler(func, 'message', 'PACKET_IN', {'x': 9})

        evt = {
            'datapath_id': '00:00:00:00:00:00:00:01',
            'type': 'PACKET_IN',
            'msg': {
                'cookie': 124
            }
        }
        self.assertFalse(h1.match(evt))
        self.assertFalse(h2.match(evt))
        evt['msg']['cookie'] = 123
        self.assertTrue(h1.match(evt))
        self.assertFalse(h2.match(evt))
        evt['type'] = 'PACKET_OUT'
        self.assertFalse(h1.match(evt))
        self.assertFalse(h2.match(evt))

    def test_message_datapath(self):
        # Test datapath_id=None filter on message handler.
        h = make_handler(func, 'message', 'PACKET_OUT', {})

        evt = {
            'datapath_id': '00:00:00:00:00:00:00:01',
            'type': 'PACKET_OUT',
            'msg': {
                'cookie': 124
            }
        }
        self.assertTrue(h.match(evt))
        evt['datapath_id'] = None
        self.assertTrue(h.match(evt))
        del evt['datapath_id']
        self.assertFalse(h.match(evt))  # only case where it makes a difference

    def test_message_no_datapath(self):
        # Test datapath_id=None filter on message handler.
        h = make_handler(func, 'message', 'PACKET_OUT', {'datapath_id': None})

        evt = {
            'datapath_id': '00:00:00:00:00:00:00:01',
            'type': 'PACKET_OUT',
            'msg': {
                'cookie': 124
            }
        }
        self.assertFalse(h.match(evt))
        evt['datapath_id'] = None
        self.assertFalse(h.match(evt))
        del evt['datapath_id']
        self.assertTrue(h.match(evt))

    def test_event_filter(self):
        h1 = make_handler(func, 'event', 'SIGNAL', {'signal': 'SIGHUP'})

        h2 = make_handler(func, 'event', 'SIGNAL', {'x': 3})

        evt = {'event': 'SIGNAL', 'signal': 'SIGTERM'}
        self.assertFalse(h1.match(evt))
        self.assertFalse(h2.match(evt))
        evt['signal'] = 'SIGHUP'
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
