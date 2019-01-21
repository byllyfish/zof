"""Test zof.Packet class."""

import pytest
from ipaddress import ip_address

from zof.packet import Packet


def test_packet():
    """Test Packet constructed from mutable dictionary."""
    data = {'a': 1}
    pkt = Packet(data)
    data['a'] = 2

    assert pkt.a == 1
    assert pkt['a'] == 1
    assert pkt.get('a') == 1

    pkt.a = 3
    assert pkt.a == 3
    assert pkt['a'] == 3
    assert pkt.get('a') == 3


def test_packet_unknown_attr():
    """Test Packet with unknown attribute access."""
    pkt = Packet(a=1)
    assert pkt.a == 1

    with pytest.raises(KeyError):
        pkt.b()

    with pytest.raises(AttributeError):
        del pkt.a


def test_packet_from_field_list():
    """Test from_field_list factory method."""
    data = [{
        'field': 'A',
        'value': 1
    }, {
        'field': 'B',
        'value': 2
    }, {
        'field': 'B',
        'value': 3
    }, {
        'field': 'B',
        'value': 4
    }, {
        'field': 'PAYLOAD',
        'value': b'xxx'
    }]
    pkt = Packet.zof_packet_from_field_list(data)
    assert pkt.a == 1
    assert pkt.b == [2, 3, 4]
    assert pkt.payload == b'xxx'


def test_packet_to_field_list():
    """Test to_field_list factory method."""
    pkt = Packet(a=1, b=[2, 3, 4], payload=b'xxx')
    data = pkt.zof_packet_to_field_list()
    assert data == [{
        'field': 'A',
        'value': 1
    }, {
        'field': 'B',
        'value': 2
    }, {
        'field': 'B',
        'value': 3
    }, {
        'field': 'B',
        'value': 4
    }, {
        'field': 'PAYLOAD',
        'value': '787878'
    }]


def test_packet_to_field_list_alternate():
    """Test to_field_list with alternate types."""
    pkt = Packet(a=ip_address('127.0.0.1'), b=ip_address('2000::1'))
    data = pkt.zof_packet_to_field_list()
    assert data == [{
        'field': 'A',
        'value': '127.0.0.1'
    }, {
        'field': 'B',
        'value': '2000::1'
    }]


def test_from_packet_in():
    """Test convert_packet_in method."""
    event = {
        'type': 'PACKET_IN',
        'msg': {
            '_pkt': [{
                'field': 'A',
                'value': 1
            }],
            'data': '0102'
        }
    }
    Packet.zof_from_packet_in(event)
    assert event['msg']['pkt'] == Packet(a=1)
    assert event['msg']['data'] == b'\x01\x02'
    assert '_pkt' not in event['msg']


def test_from_packet_in_pos():
    """Test convert_packet_in method with x_pkt_pos."""
    event = {
        'type': 'PACKET_IN',
        'msg': {
            '_pkt': [{
                'field': 'A',
                'value': 0x0102
            }, {
                'field': 'X_PKT_POS',
                'value': 2
            }],
            'data':
            '01020304'
        }
    }
    Packet.zof_from_packet_in(event)
    assert event['msg']['pkt'] == Packet(a=0x0102, payload=b'\x03\x04')
    assert event['msg']['data'] == b'\x01\x02\x03\x04'
    assert '_pkt' not in event['msg']


def test_from_packet_in_partial():
    """Test zof_from_packet_in method for incomplete event."""
    event = {'type': 'PACKET_IN', 'msg': {'data': '0102'}}
    Packet.zof_from_packet_in(event)
    assert event['msg']['data'] == b'\x01\x02'
    assert event['msg']['pkt'] == Packet()
    assert '_pkt' not in event['msg']


def test_to_packet_out():
    """Test zof_to_packet_out method."""
    event = {
        'type': 'PACKET_OUT',
        'msg': {
            'pkt': Packet(a=1, payload=b'\x01\x02')
        }
    }
    Packet.zof_to_packet_out(event)
    assert event['msg']['_pkt'] == [{'field': 'A', 'value': 1}]
    assert event['msg']['_pkt_data'] == '0102'


def test_packet_properties():
    """Test _packet_property accessors."""
    pkt = Packet()
    pkt.ip_ttl = 64
    assert pkt.nx_ip_ttl == 64
    assert pkt.ip_ttl == 64
    assert pkt.nx_ip_ttl == 64
    assert pkt.hop_limit == 64

    pkt.hop_limit = 2
    assert pkt.nx_ip_ttl == 2
    assert pkt.ip_ttl == 2

    data = pkt.zof_packet_to_field_list()
    assert data == [{
        'field': 'NX_IP_TTL',
        'value': 2
    }]
