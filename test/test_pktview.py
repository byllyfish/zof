import unittest
from pylibofp.pktview import make_pktview, pktview_from_list, pktview_to_list


class PktViewTestCase(unittest.TestCase):

    def test_init(self):
        pkt = make_pktview(a = 1, b = 2)
        self.assertEqual(pkt.a, 1)
        self.assertEqual(pkt.b, 2)

    def test_basic(self):
        data = [
            dict(field='A', value='a'),
            dict(field='B', value=2)
        ]
        pkt = pktview_from_list(data)
        self.assertEqual(pkt.a, 'a')
        self.assertEqual(pkt.b, 2)

        fields = pktview_to_list(pkt)
        fields.sort(key=_by_field)
        self.assertEqual(fields, data)

    def test_invalid_init(self):
        with self.assertRaises(ValueError):
            pkt = pktview_from_list(dict(A='a'))

    def test_to_list(self):
        data = dict(a = 'a', b = 2, c='ddd')
        fields = pktview_to_list(data)
        fields.sort(key=_by_field)
        self.assertEqual(fields, [dict(field='A', value='a'), dict(field='B', value=2), dict(field='C', value='ddd')])


    def test_aliases(self):
        pkt = make_pktview()
        pkt.hoplimit = 5
        self.assertEqual(pkt.nx_ip_ttl, 5)
        pkt.nx_ip_ttl = 10
        self.assertEqual(pkt.hoplimit, 10)
        del pkt.hoplimit
        self.assertFalse('nx_ip_ttl' in pkt)

    def test_get_protocol(self):
        pkt = make_pktview(ipv4_src='1.2.3.4', eth_type=0x0800)
        self.assertEqual(pkt.get_protocol('IPV4'), pkt)
        self.assertFalse(pkt.get_protocol('IPV6'))
        self.assertFalse(pkt.get_protocol('ARP'))
        self.assertEqual(pkt.get_protocol('ethernet'), pkt)


def _by_field(item):
    return item['field']
