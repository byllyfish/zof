import unittest
from zof.ofctl import convert_from_ofctl


class TestOfctl(unittest.TestCase):
    def test_tcpv4(self):
        ofctl = {
            'dl_src': '00:00:00:00:00:01',
            'dl_dst': '00:00:00:00:00:02',
            'dl_type': 0x0800,
            'nw_src': '192.168.1.1',
            'nw_dst': '192.168.1.2',
            'nw_proto': 6,
            'tp_src': 1001,
            'tp_dst': 1002,
            'other_field': 'other_value'
        }
        result = convert_from_ofctl(ofctl)
        self.assertEqual(
            result, {
                'eth_src': '00:00:00:00:00:01',
                'eth_dst': '00:00:00:00:00:02',
                'eth_type': 0x0800,
                'ipv4_src': '192.168.1.1',
                'ipv4_dst': '192.168.1.2',
                'ip_proto': 6,
                'tcp_src': 1001,
                'tcp_dst': 1002,
                'other_field': 'other_value'
            })

    def test_nw_src_dup(self):
        # Test duplicate field (nw_src = ipv4_src)
        ofctl = {
            'nw_src': '192.168.1.1',
            'ipv4_src': '192.168.1.2',
        }
        with self.assertRaisesRegex(ValueError, 'Duplicate ofctl field'):
            convert_from_ofctl(ofctl)

    def test_dl_vlan(self):
        ofctl = {
            'dl_src': '00:00:00:00:00:01',
            'dl_dst': '00:00:00:00:00:02',
            'dl_vlan': '0x123',
            'dl_type': 0x0800
        }
        result = convert_from_ofctl(ofctl, validate=True)
        self.assertEqual(
            result, {
                'eth_src': '00:00:00:00:00:01',
                'eth_dst': '00:00:00:00:00:02',
                'eth_type': 0x0800,
                'vlan_vid': 0x1123
            })

    def test_vlan_zero(self):
        ofctl = {'dl_vlan': '0x0'}
        result = convert_from_ofctl(ofctl)
        self.assertEqual(result, {'vlan_vid': 0})

        ofctl = {'dl_vlan': 0x64}
        result = convert_from_ofctl(ofctl)
        self.assertEqual(result, {'vlan_vid': 0x1064})

    def test_tp_src(self):
        # If ip_proto is not specified, default to 'tcp'
        ofctl = {'tp_src': 80, 'tp_dst': 81}
        result = convert_from_ofctl(ofctl)
        self.assertEqual(result, {'tcp_src': 80, 'tcp_dst': 81})

    def test_tp_fail(self):
        # If ip_proto is not supported, raise ValueError.
        ofctl = {'nw_proto': 2, 'tp_src': 80, 'tp_dst': 81}
        with self.assertRaises(ValueError):
            convert_from_ofctl(ofctl)

    def test_tp_dst(self):
        # UDP
        ofctl = {'dl_type': 0x0800, 'nw_proto': 17, 'tp_dst': 53}
        result = convert_from_ofctl(ofctl)
        self.assertEqual(result, {
            'eth_type': 0x0800,
            'ip_proto': 17,
            'udp_dst': 53
        })

        ofctl['nw_proto'] = 6  # TCP
        result = convert_from_ofctl(ofctl)
        self.assertEqual(result, {
            'eth_type': 0x0800,
            'ip_proto': 6,
            'tcp_dst': 53
        })

        ofctl['nw_proto'] = 132  # SCTP
        result = convert_from_ofctl(ofctl)
        self.assertEqual(result, {
            'eth_type': 0x0800,
            'ip_proto': 132,
            'sctp_dst': 53
        })

    def test_empty(self):
        result = convert_from_ofctl(None)
        self.assertEqual(result, None)

        result = convert_from_ofctl({})
        self.assertEqual(result, {})

    def test_arp(self):
        ofctl = {
            'dl_src': '00:00:00:00:00:01',
            'dl_dst': '00:00:00:00:00:02',
            'dl_type': 0x0806,
            'arp_op': 1,
            'nw_src': '192.168.1.1',
            'nw_dst': '192.168.1.2'
        }
        result = convert_from_ofctl(ofctl)
        self.assertEqual(
            result, {
                'eth_src': '00:00:00:00:00:01',
                'eth_dst': '00:00:00:00:00:02',
                'eth_type': 0x0806,
                'arp_op': 1,
                'arp_spa': '192.168.1.1',
                'arp_tpa': '192.168.1.2',
            })

    def test_validate_invalid(self):
        ofctl = {
            'dl_src': '00:00:00:00:00:01',
            'dl_dst': '00:00:00:00:00:02',
            'dl_type': 0x0800,
            'nw_src': '192.168.1.1',
            'nw_dst': '192.168.1.2',
            'nw_proto': 6,
            'tp_src': 1001,
            'tp_dst': 1002,
            'other_field': 'other_value'
        }
        with self.assertRaisesRegex(ValueError, 'other_field'):
            convert_from_ofctl(ofctl, validate=True)

        ofctl = {'udp_src': 'x'}
        with self.assertRaisesRegex(ValueError, 'udp_src: x'):
            convert_from_ofctl(ofctl, validate=True)

    def test_validate_masked(self):
        ofctl = {'udp_src': '123/0xFF'}
        result = convert_from_ofctl(ofctl, validate=True)
        self.assertEqual(result, {'udp_src': '123/0xFF'})

        ofctl = {'udp_src': '123/70/12'}
        with self.assertRaisesRegex(ValueError, 'udp_src: 123/70/12'):
            convert_from_ofctl(ofctl, validate=True)
