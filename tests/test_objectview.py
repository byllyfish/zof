import unittest
from pylibofp.objectview import ObjectView


def _test_dict():
    return dict(a=1, b=2, z=dict(y=9))


class ObjectViewTestCase(unittest.TestCase):

    def setUp(self):
        self.obj = ObjectView(_test_dict())

    def test_init(self):
        self.assertEqual(self.obj.__dict__, _test_dict())

    def test_property(self):
        self.assertEqual(self.obj.a, 1)
        self.assertEqual(self.obj.b, 2)
        self.assertEqual(self.obj.z, {'y': 9})
        with self.assertRaisesRegex(AttributeError, 'c'):
            print(self.obj.c)
        # Nested dictionaries aren't wrapped.
        with self.assertRaisesRegex(AttributeError, "'dict' object has no attribute 'y'"):
            print(self.obj.z.y)

    def test_setproperty(self):
        self.assertEqual(self.obj.a, 1)
        self.obj.a = 5
        self.assertEqual(self.obj.a, 5)
        self.obj.a = 1
        self.assertEqual(self.obj.a, 1)
        self.obj.c = 4
        self.assertEqual(self.obj.c, 4)
        del self.obj['c']
        with self.assertRaisesRegex(AttributeError, 'c'):
            print(self.obj.c)

    def test_contains(self):
        self.assertTrue('a' in self.obj)
        self.assertTrue('b' in self.obj)
        self.assertTrue('c' not in self.obj)
        self.assertFalse(1 in self.obj)

    def test_len(self):
        self.assertEqual(len(self.obj), 3)

    def test_iteration(self):
        count = 0
        for key in self.obj:
            self.assertIn(key, self.obj)
            self.assertIn(key, ['a', 'b', 'z'])
            count += 1
        self.assertEqual(count, 3)

    def test_getitem(self):
        self.assertEqual(self.obj['a'], 1)
        self.assertEqual(self.obj['b'], 2)
        with self.assertRaisesRegex(KeyError, 'c'):
            print(self.obj['c'])

    def test_setitem(self):
        self.assertEqual(self.obj['a'], 1)
        self.obj['a'] = 6
        self.assertEqual(self.obj['a'], 6)
        self.obj['a'] = 1
        self.assertEqual(self.obj['a'], 1)
        self.obj['d'] = 4
        self.assertEqual(self.obj['d'], 4)
        del self.obj['d']
        with self.assertRaisesRegex(KeyError, 'd'):
            print(self.obj['d'])

    def test_delitem(self):
        with self.assertRaisesRegex(AttributeError, 'aa'):
            print(self.obj.aa)
        self.obj.aa = 9
        self.assertEqual(self.obj.aa, 9)
        del self.obj.aa
        with self.assertRaisesRegex(AttributeError, 'aa'):
            print(self.obj.aa)

    def test_eq(self):
        self.assertEqual(self.obj, _test_dict())
        self.assertTrue(self.obj == _test_dict())
        self.assertTrue(_test_dict() == self.obj)
        self.assertEqual(self.obj, ObjectView(_test_dict()))
        self.assertTrue(self.obj == ObjectView(_test_dict()))
        
    def test_neq(self):
        self.assertNotEqual(self.obj, {})
        self.assertFalse(self.obj != _test_dict())
        self.assertFalse(_test_dict() != self.obj)
        self.assertNotEqual(self.obj, ObjectView({}))
        self.assertFalse(self.obj != ObjectView(_test_dict()))
    
    def test_bool(self):
        self.assertTrue(self.obj)

    def test_str(self):
        o = ObjectView(dict(q=[1, 2, 3]))
        s = str(o)
        self.assertEqual(s, '{"q":[1,2,3]}')

    def test_json_dumps(self):
        o = ObjectView(dict(q=[1, 2, 3]))
        # json_dumps is a static method.
        s = o.json_dumps(o)
        self.assertEqual(s, '{"q":[1,2,3]}')


