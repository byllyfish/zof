import unittest
from pylibofp.ofctl import convert_from_ofctl


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
        self.assertEqual(result, {
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
