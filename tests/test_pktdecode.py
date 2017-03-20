import unittest
from pylibofp.pktdecode import PktDecode


class PktDecodeTestCase(unittest.TestCase):

    def test_basic(self):
        data = [
            dict(field='A', value='a'),
            dict(field='B', value=2)
        ]
        pkt = PktDecode(data)
        self.assertEqual(pkt.a, 'a')
        self.assertEqual(pkt.b, 2)

        fields = PktDecode.to_list(pkt)
        fields.sort(key=_by_field)
        self.assertEqual(fields, data)

    def test_invalid_init(self):
        with self.assertRaises(ValueError):
            pkt = PktDecode(dict(A='a'))

    def test_to_list(self):
        data = dict(a = 'a', b = 2, c='ddd')
        fields = PktDecode.to_list(data)
        fields.sort(key=_by_field)
        self.assertEqual(fields, [dict(field='A', value='a'), dict(field='B', value=2), dict(field='C', value='ddd')])


def _by_field(item):
    return item['field']
