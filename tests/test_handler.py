import unittest
from pylibofp.handler import make_handler




class HandlerTestCase(unittest.TestCase):

    def test_make_handler(self):
        h = make_handler(func, 'message', 'FEATURES_REQUEST')
        self.assertTrue(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)
        

    def test_bad_func(self):
        h = make_handler(bad_func, 'message', 'FEATURES_REQUEST')
        self.assertFalse(h.verify())
        self.assertEqual('message', h.type)
        self.assertEqual('FEATURES_REQUEST', h.subtype)        
    

def func(event):
    pass

def bad_func():
    pass
