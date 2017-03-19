import unittest
from pylibofp.pktdecode import PktDecode


class PktDecodeTestCase(unittest.TestCase):

    def test_init(self):
        data = [
            dict(field='A', value='a'),
            dict(field='B', value=2)
        ]
        pkt = PktDecode(data)
        self.assertEqual(pkt.a, 'a')
        self.assertEqual(pkt.b, 2)

    def test_invalid_init(self):
        pkt = PktDecode(dict(A='a'))

