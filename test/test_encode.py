import unittest
import zof
from zof.objectview import make_objectview


class EncodeTestCase(unittest.TestCase):

    def test_empty(self):
        with self.assertRaisesRegex(ValueError, r'YAML:1:1: error: not a document'):
            zof.encode('')

        with self.assertRaisesRegex(ValueError, r'YAML:1:1: error: not a document'):
            zof.encode('---\n\n...\n')

    def test_hello(self):
        result = zof.encode('type: HELLO\nversion: 1')
        self.assertEqual(result, b'\x01\x00\x00\x08\x00\x00\x00\x00')

        result = zof.encode('type: HELLO')
        self.assertEqual(result, b'\x04\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00\x10')

        result = zof.encode('type: HELLO', version=0)
        self.assertEqual(result, b'\x06\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00~')

    def test_hello_error(self):
        with self.assertRaisesRegex(ValueError, r"YAML:1:1: error: missing required key 'type'"):
            zof.encode('typ: HELLO')

        with self.assertRaisesRegex(ValueError, r'YAML:1:7: error: unknown value "HELO" Did you mean "HELLO"?'):
            zof.encode('type: HELO')

    def test_hello_object(self):
        result = zof.encode({'type': 'HELLO', 'version': 4})
        self.assertEqual(result, b'\x04\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00\x10')

        result = zof.encode(make_objectview({'type': 'HELLO', 'version': 4}))
        self.assertEqual(result, b'\x04\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00\x10')
