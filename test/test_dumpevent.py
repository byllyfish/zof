import unittest
from zof.event import dump_event, Event


class DumpEventTestCase(unittest.TestCase):
    def test_empty_dict(self):
        # Test empty event as Python object.
        data = dump_event({})
        self.assertIsInstance(data, bytes)
        self.assertEqual(data, b'{}')

    def test_empty_dict2(self):
        # Test empty event as Event object.
        data = dump_event(Event({}))
        self.assertIsInstance(data, bytes)
        self.assertEqual(data, b'{}')

    def test_hello(self):
        # Test hello event as Python object.
        data = dump_event(dict(msg=dict(type='foo')))
        self.assertIsInstance(data, bytes)
        self.assertEqual(data, b'{"msg":{"type":"foo"}}')

    def test_string(self):
        # Test event as YAML string.
        data = dump_event('type: string\nmsg: "{}"')
        self.assertIsInstance(data, bytes)
        self.assertEqual(data, b'type: string\nmsg: "{}"')

    def test_bytes(self):
        # Test that bytes values are converted to hex strings.
        data = dump_event({'x': b'12345'})
        self.assertEqual(data, b'{"x":"3132333435"}')

    def test_nonserializable(self):
        # Test a value that isn't JSON serializable.
        with self.assertRaisesRegex(TypeError,
                                    "Value .+ is not JSON serializable"):
            dump_event({'x': set()})

    def test_utf8(self):
        # Test that Unicode/UTF-8 works.
        data = dump_event({'x': '\u20AC\U00010302\U0010fffd'})
        self.assertEqual(
            data, b'{"x":"\xe2\x82\xac\xf0\x90\x8c\x82\xf4\x8f\xbf\xbd"}')

    def test_getstate(self):
        # Test custom class with __getstate__.
        class Foo:
            def __init__(self):
                self.y = 1

            def __getstate__(self):
                return self.__dict__

        data = dump_event({'x': Foo()})
        self.assertEqual(data, b'{"x":{"y":1}}')
