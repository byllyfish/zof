import unittest
from zof.event import make_event, Event


class MakeEventTestCase(unittest.TestCase):
    def test_empty(self):
        with self.assertRaises(ValueError):
            make_event()

    def test_event(self):
        obj = make_event(event='test')
        self.assertIsInstance(obj, Event)
        self.assertEqual(obj.event, 'test')

    def test_dict_member(self):
        obj = make_event(event='test', options={'a': 5})
        self.assertIsInstance(obj, Event)
        self.assertEqual(obj.event, 'test')
        self.assertIsInstance(obj.options, Event)
        self.assertEqual(obj.options['a'], 5)
        self.assertEqual(obj.options.a, 5)

    def test_event_member(self):
        obj = make_event(event='test', params=make_event(event='inner', a=6))
        self.assertIsInstance(obj, Event)
        self.assertEqual(obj.event, 'test')
        self.assertEqual(obj.params, {'event': 'inner', 'a': 6})
        self.assertEqual(obj.params.event, 'inner')
        self.assertEqual(obj.params.a, 6)

    def test_dict2_member(self):
        obj = make_event(options={'a': {'b': {'c': 7}}}, event='test')
        self.assertIsInstance(obj, Event)
        self.assertEqual(obj.event, 'test')
        self.assertIsInstance(obj.options, Event)
        self.assertIsInstance(obj.options.a, Event)
        self.assertIsInstance(obj.options.a.b, Event)
        self.assertEqual(obj.options.a.b.c, 7)
