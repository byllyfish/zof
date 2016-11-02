import unittest
from pylibofp.event import make_event, Event

class MakeEventTestCase(unittest.TestCase):

    def test_empty(self):
        event = make_event()
        self.assertIsInstance(event, Event)
        self.assertEqual(event, {})

    def test_event(self):
        obj = make_event(event='test')
        self.assertIsInstance(obj, Event)
        self.assertEqual(obj.event, 'test')

    def test_dict_member(self):
        obj = make_event(options={'a':5})
        self.assertIsInstance(obj, Event)
        self.assertIsInstance(obj.options, Event)
        self.assertEqual(obj.options['a'], 5)
        self.assertEqual(obj.options.a, 5)

    def test_event_member(self):
        obj = make_event(params=make_event(a=6))
        self.assertIsInstance(obj, Event)
        self.assertEqual(obj.params, {'a':6})
        self.assertEqual(obj.params.a, 6)

    def test_dict2_member(self):
        obj = make_event(options={'a':{'b':{'c':7}}})
        self.assertIsInstance(obj, Event)
        self.assertIsInstance(obj.options, Event)
        self.assertIsInstance(obj.options.a, Event)
        self.assertIsInstance(obj.options.a.b, Event)
        self.assertEqual(obj.options.a.b.c, 7)
