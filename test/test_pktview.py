import unittest
from ipaddress import IPv4Address, IPv6Address, ip_address
from zof.pktview import make_pktview, pktview_from_list, pktview_to_list, PktView, pktview_alias, pktview_from_ofctl, convert_slash_notation


class PktViewTestCase(unittest.TestCase):
    def test_init(self):
        pkt = make_pktview(a=1, b=2)
        self.assertEqual(pkt.a, 1)
        self.assertEqual(pkt.b, 2)

    def test_basic(self):
        data = [dict(field='A', value='a'), dict(field='B', value=2)]
        pkt = pktview_from_list(data)
        self.assertEqual(pkt.a, 'a')
        self.assertEqual(pkt.b, 2)

        fields = pktview_to_list(pkt)
        fields.sort(key=_by_field)
        self.assertEqual(fields, data)

    def test_invalid_init(self):
        with self.assertRaises(ValueError):
            pktview_from_list(dict(A='a'))

    def test_from_list(self):
        data = [dict(field='A', value=5, mask=255)]
        pkt = pktview_from_list(data)
        self.assertEqual(pkt, {'a': (5, 255)})

        pkt = pktview_from_list(data, slash_notation=True)
        self.assertEqual(pkt, {'a': '5/255'})

        with self.assertRaises(ValueError):
            pktview_from_list([{'field': 'PAYLOAD', 'value': '1234'}])

    def test_to_list(self):
        data = dict(a='a', b=2, c='ddd')
        fields = pktview_to_list(data)
        fields.sort(key=_by_field)
        self.assertEqual(
            fields, [
                dict(
                    field='A', value='a'), dict(
                        field='B', value=2), dict(
                            field='C', value='ddd')
            ])

        with self.assertRaisesRegex(ValueError, r'len\(tuple\) != 2'):
            pktview_to_list({'a': (1, 2, 3)})

    def test_alias_attr(self):
        pkt = make_pktview()
        pkt.hop_limit = 5
        self.assertEqual(pkt.nx_ip_ttl, 5)
        self.assertEqual(pkt['nx_ip_ttl'], 5)
        self.assertEqual(pkt['hop_limit'], 5)

        pkt.nx_ip_ttl = 10
        self.assertEqual(pkt.hop_limit, 10)
        self.assertTrue('hop_limit' in pkt)
        del pkt.hop_limit
        self.assertFalse('nx_ip_ttl' in pkt)

    def test_alias_subscript(self):
        pkt = make_pktview()
        pkt['hop_limit'] = 6
        self.assertEqual(pkt['hop_limit'], 6)
        self.assertEqual(pkt.hop_limit, 6)
        self.assertEqual(pkt.nx_ip_ttl, 6)
        self.assertTrue('hop_limit' in pkt)
        self.assertTrue('nx_ip_ttl' in pkt)
        del pkt['hop_limit']
        self.assertFalse('hop_limit' in pkt)
        self.assertFalse('nx_ip_ttl' in pkt)
        with self.assertRaisesRegex(KeyError, 'hop_limit'):
            del pkt['hop_limit']

    def test_get_protocol(self):
        pkt = make_pktview(ipv4_src='1.2.3.4', eth_type=0x0800)
        self.assertEqual(pkt.get_protocol('IPV4'), pkt)
        self.assertFalse(pkt.get_protocol('IPV6'))
        self.assertFalse(pkt.get_protocol('ARP'))
        self.assertEqual(pkt.get_protocol('ethernet'), pkt)

    def test_pktview_alias_identity(self):
        # Test that identity alias doesn't recurse forever.
        class SubPktView(PktView):
            ip = pktview_alias('ip')

        pkt = SubPktView({})
        pkt.ip = '1.2.3.4'
        self.assertEqual(pkt.ip, '1.2.3.4')
        self.assertTrue('ip' in pkt)
        del pkt.ip
        self.assertFalse('ip' in pkt)

    def test_pktview_alias_converter(self):
        class SubPktView(PktView):
            ip = pktview_alias('ip', ip_address)

        pkt = SubPktView({})
        pkt.ip = '1.2.3.4'
        self.assertIsInstance(pkt.ip, IPv4Address)
        self.assertEqual(pkt.ip, ip_address('1.2.3.4'))
        self.assertTrue('ip' in pkt)
        del pkt.ip
        self.assertFalse('ip' in pkt)

    def test_pktview_items(self):
        pkt = make_pktview(ipv4_src='1.2.3.4', eth_type=0x0800)
        items = list(pkt.items())
        items.sort()
        self.assertEqual(items,
                         [('eth_type', 0x0800), ('ipv4_src', '1.2.3.4')])

    def test_pktview_from_ofctl(self):
        data = dict(dl_type=0x0800, nw_proto=6, tp_dst=80)
        pkt = pktview_from_ofctl(data)
        self.assertEqual(pkt, {'ip_proto': 6, 'eth_type': 2048, 'tcp_dst': 80})

        data = dict(dl_dst='ab:cd:00:00:00:00/ff:ff:00:00:00:00')
        pkt = pktview_from_ofctl(data)
        self.assertEqual(pkt,
                         {'eth_dst': 'ab:cd:00:00:00:00/ff:ff:00:00:00:00'})
        items = pktview_to_list(pkt)
        self.assertEqual(items, [{
            'value': 'ab:cd:00:00:00:00',
            'field': 'ETH_DST',
            'mask': 'ff:ff:00:00:00:00'
        }])

    def test_convert_slash_notation(self):
        self.assertEqual(
            convert_slash_notation('ETH_SRC',
                                   '0e:dc:00:00:00:00/ff:ff:00:00:00:00'),
            ('0e:dc:00:00:00:00', 'ff:ff:00:00:00:00'))
        self.assertEqual(
            convert_slash_notation('IPV4_SRC', '1.2.3.4/255.255.0.0'),
            (IPv4Address('1.2.3.4'), IPv4Address('255.255.0.0')))
        self.assertEqual(
            convert_slash_notation('IPV4_SRC', '1.2.3.4/16'),
            (IPv4Address('1.2.3.4'), IPv4Address('255.255.0.0')))
        self.assertEqual(
            convert_slash_notation('IPV6_SRC', '2001::1/ffff::'),
            (IPv6Address('2001::1'), IPv6Address('ffff::')))
        self.assertEqual(
            convert_slash_notation('IPV6_SRC', '2001::1/16'),
            (IPv6Address('2001::1'), IPv6Address('ffff::')))

        addr = IPv4Address('1.2.3.4')
        self.assertIs(convert_slash_notation('IPV4_SRC', addr), addr)

        with self.assertRaises(ValueError):
            convert_slash_notation('IPV4_SRC', '1.2.3.4/64')

    def test_description(self):
        pkt = make_pktview(ip_proto=6, eth_type=0x0800)
        self.assertEqual(pkt.get_description(), 'TCPv4')
        pkt = make_pktview(ip_proto=1, eth_type=0x0800)
        self.assertEqual(pkt.get_description(), 'ICMPv4')
        pkt = make_pktview(ip_proto=2, eth_type=0x0800)
        self.assertEqual(pkt.get_description(), 'IGMPv4')
        pkt = make_pktview(ip_proto=17, eth_type=0x0800)
        self.assertEqual(pkt.get_description(), 'UDPv4')
        pkt = make_pktview(ip_proto=76, eth_type=0x0800)
        self.assertEqual(pkt.get_description(), 'IPv4:76')
        pkt = make_pktview(ip_proto=6, eth_type=0x86dd)
        self.assertEqual(pkt.get_description(), 'TCPv6')
        pkt = make_pktview(ip_proto=58, eth_type=0x86dd)
        self.assertEqual(pkt.get_description(), 'ICMPv6')
        pkt = make_pktview(ip_proto=17, eth_type=0x86dd)
        self.assertEqual(pkt.get_description(), 'UDPv6')
        pkt = make_pktview(eth_type=25)
        self.assertEqual(pkt.get_description(), 'ETH:25')
        pkt = make_pktview(eth_type=0x0800)
        self.assertEqual(pkt.get_description(), 'IPv4:None')
        pkt = make_pktview(ip_proto=79, eth_type=0x86dd)
        self.assertEqual(pkt.get_description(), 'IPv6:79')
        pkt = make_pktview(eth_type=0x0806, arp_op=1)
        self.assertEqual(pkt.get_description(), 'ARP:REQ')
        pkt = make_pktview(eth_type=0x0806, arp_op=2)
        self.assertEqual(pkt.get_description(), 'ARP:REPLY')
        pkt = make_pktview(eth_type=0x0806, arp_op=3)
        self.assertEqual(pkt.get_description(), 'ARP:3')
        pkt = make_pktview(eth_type=0x88cc)
        self.assertEqual(pkt.get_description(), 'LLDP')


def _by_field(item):
    return item['field']
