import unittest
from pylibofp.handler import make_handler




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
        self.assertEqual(None, h.help_brief())
        self.assertEqual(None, h.help())

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
        self.assertEqual(None, h.help_brief())
        self.assertEqual(None, h.help())    


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
