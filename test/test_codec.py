import unittest
import zof
import codecs
from zof.codec import encode, decode, OFTR_ENCODE, _oftr_call
from zof.exception import CodecError


class CodecTestCase(unittest.TestCase):
    def test_empty(self):
        with self.assertRaisesRegex(ValueError,
                                    r'YAML:1:1: error: not a document'):
            encode('')

        with self.assertRaisesRegex(ValueError,
                                    r'YAML:1:1: error: not a document'):
            encode('---\n\n...\n')

    def test_oftr_call(self):
        result = _oftr_call(OFTR_ENCODE, b'type: HELLO', 4)
        self.assertEqual(
            result,
            b'\x06\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00~')

    def test_hello(self):
        result = encode('type: HELLO\nversion: 1')
        self.assertEqual(result, b'\x01\x00\x00\x08\x00\x00\x00\x00')

        result = encode('type: HELLO')
        self.assertEqual(
            result,
            b'\x04\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00\x10'
        )

        result = encode('type: HELLO', version=0)
        self.assertEqual(
            result,
            b'\x06\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00~')

    def test_hello_error(self):
        with self.assertRaisesRegex(
                ValueError, r"YAML:1:1: error: missing required key 'type'"):
            encode('typ: HELLO')

        with self.assertRaisesRegex(
                ValueError,
                r'YAML:1:7: error: unknown value "HELO" Did you mean "HELLO"?'
        ):
            encode('type: HELO')

    def test_hello_object(self):
        result = encode({'type': 'HELLO', 'version': 4})
        self.assertEqual(
            result,
            b'\x04\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00\x10'
        )

    def test_decode_hello(self):
        result = decode(b'\x01\x00\x00\x08\x00\x00\x00\x00')
        self.assertEqual(result, """---
type:            HELLO
xid:             0x00000000
version:         0x01
msg:             
  versions:        [  ]
...
""")

        result = decode(
            b'\x04\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00\x10'
        )
        self.assertEqual(result, """---
type:            HELLO
xid:             0x00000000
version:         0x04
msg:             
  versions:        [ 4 ]
...
""")

        result = decode(
            b'\x06\x00\x00\x10\x00\x00\x00\x00\x00\x01\x00\x08\x00\x00\x00~')
        self.assertEqual(result, """---
type:            HELLO
xid:             0x00000000
version:         0x06
msg:             
  versions:        [ 1, 2, 3, 4, 5, 6 ]
...
""")

    def test_codec(self):
        result = 'type: HELLO\nversion: 1'.encode('openflow')
        self.assertEqual(result, b'\x01\x00\x00\x08\x00\x00\x00\x00')

        result = b'\x01\x00\x00\x08\x00\x00\x00\x00'.decode('openflow')
        self.assertEqual(result, """---
type:            HELLO
xid:             0x00000000
version:         0x01
msg:             
  versions:        [  ]
...
""")

    def test_codec_exception(self):
        try:
            'type: PACKET_IN'.encode('openflow')
        except ValueError as ex:
            self.assertIsNone(ex.__cause__)
            self.assertIsInstance(ex, CodecError)

        try:
            codecs.encode('type: PACKET_IN', 'openflow')
        except ValueError as ex:
            self.assertIsNone(ex.__cause__)
            self.assertIsInstance(ex, CodecError)
