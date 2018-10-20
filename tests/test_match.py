"""Test zof.Match class."""

from ipaddress import IPv4Address, IPv6Address

from zof.match import Match


def test_match_to_list():
    """Test Match."""
    match = Match(a=1)
    assert match.to_list() == [{'field': 'A', 'value': 1}]

    match = Match(ipv4_dst='1.2.3.4/24')
    assert match.to_list() == [{
        'field': 'IPV4_DST',
        'value': IPv4Address('1.2.3.4'),
        'mask': IPv4Address('255.255.255.0')
    }]

    match = Match(ipv6_dst='2000::1/64')
    assert match.to_list() == [{
        'field': 'IPV6_DST',
        'value': IPv6Address('2000::1'),
        'mask': IPv6Address('ffff:ffff:ffff:ffff::')
    }]

    match = Match(tcp_dst='80/0xFF')
    assert match.to_list() == [{
        'field': 'TCP_DST',
        'value': '80',
        'mask': '0xFF'
    }]
