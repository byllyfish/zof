import unittest
import ipaddress
import argparse
import json
from zof.objectview import ObjectView, to_json, from_json, make_objectview


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
        with self.assertRaisesRegex(AttributeError,
                                    "'dict' object has no attribute 'y'"):
            print(self.obj.z.y)

    def test_special_property(self):
        obj = ObjectView({'get': 42, 'to_json': 'foo'})
        self.assertEqual(obj['get'], 42)
        self.assertEqual(obj.get, 42)

        self.assertEqual(obj.to_json, 'foo')
        obj.to_json = 4
        self.assertEqual(obj['to_json'], 4)
        self.assertEqual(obj.to_json, 4)
        del obj.to_json
        with self.assertRaises(AttributeError):
            print(obj.to_json)

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
        self.assertFalse('zz' in self.obj)
        with self.assertRaisesRegex(TypeError,
                                    'attribute name must be string'):
            self.assertFalse(1 in self.obj)

    def test_len(self):
        self.assertEqual(len(self.obj), 3)

    def test_bool(self):
        self.assertTrue(self.obj)
        empty = ObjectView({})
        self.assertTrue(empty)
        self.assertEqual(len(empty), 0)

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
        with self.assertRaisesRegex(AttributeError, 'bb'):
            del self.obj.bb
        with self.assertRaisesRegex(KeyError, 'dd'):
            del self.obj['dd']

    def test_callable(self):
        self.assertEqual(self.obj('a'), 1)
        self.assertEqual(self.obj('b'), 2)
        self.assertEqual(self.obj('c'), None)
        self.assertEqual(self.obj('c', default=5), 5)

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

    def test_str(self):
        obj = ObjectView(dict(q=[1, 2, 3]))
        self.assertEqual(str(obj), '{"q":[1,2,3]}')

    def test_repr(self):
        obj = ObjectView(dict(q=[1, 2, 3]))
        self.assertEqual(repr(obj), "{'q': [1, 2, 3]}")

    def test_to_json(self):
        obj = ObjectView(dict(q=[1, 2, 3]))
        self.assertEqual(to_json(obj), '{"q":[1,2,3]}')

    def test_from_json(self):
        obj = from_json(b'{"a":1}')
        self.assertEqual(obj, {'a': 1})

    def test_ip_address(self):
        obj = ObjectView(
            dict(a=[
                ipaddress.ip_address('10.1.2.3'), ipaddress.ip_address(
                    '2001::1')
            ]))
        self.assertEqual(to_json(obj), '{"a":["10.1.2.3","2001::1"]}')

    def test_argparse_namespace(self):
        args = argparse.Namespace(b=3)
        obj = ObjectView(dict(a=args))
        self.assertEqual(to_json(obj), '{"a":{"b":3}}')

    def test_make_objectview(self):
        data = dict(a=1, b=2)
        obj = make_objectview(data)
        self.assertEqual(obj, data)

        data = dict(a=dict(b=5), b=[dict(c=6), dict(c=7)])
        obj = make_objectview(data)
        self.assertEqual(obj.a.b, 5)
        self.assertEqual(obj.b[1].c, 7)

        # Object is already an ObjectView
        new_obj = make_objectview(obj)
        self.assertIs(new_obj, obj)

    def test_make_objecview_argparse(self):
        args = argparse.Namespace(x=1, y='2')
        obj = make_objectview(args)
        self.assertEqual(obj.x, 1)
        self.assertEqual(obj.y, '2')

    def test_format(self):
        data = dict(x=dict(a=1))
        obj = make_objectview(data)
        self.assertEqual('{:2s}'.format(obj),
                         '{\n  "x": {\n    "a": 1\n  }\n}')
        with self.assertRaisesRegex(ValueError,
                                    'does not support format_spec'):
            '{:4d}'.format(obj)

    def test_std_json(self):
        data = dict(c=5)
        obj = make_objectview(data)
        with self.assertRaisesRegex(TypeError, 'is not JSON serializable'):
            # python's standard json module does not support objectview.
            json.dumps(obj)
