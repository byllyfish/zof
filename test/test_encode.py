import unittest
import zof


class EncodeTestCase(unittest.TestCase):

    @unittest.skip('requires newer oftr')
    def test_hello(self):
        result = zof.encode('type: HELLO\nversion: 1')
        self.assertEqual(result, b'\x01\x00\x00\x08\x00\x00\x00\x00')
