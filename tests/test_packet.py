import pytest
from zoflite.packet import Packet


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
    data = [{'field': 'A', 'value': 1}, 
            {'field': 'B', 'value': 2}, 
            {'field': 'B', 'value': 3},
            {'field': 'B', 'value': 4},
            {'field': 'PAYLOAD', 'value': b'xxx'}]
    pkt = Packet.zof_from_field_list(data)
    assert pkt.a == 1
    assert pkt.b == [2, 3, 4]
    assert pkt.payload == b'xxx'


def test_packet_to_field_list():
    """Test to_field_list factory method."""
    pkt = Packet(a=1, b=[2, 3, 4], payload=b'xxx')
    data = pkt.zof_to_field_list()
    assert data == [{'field': 'A', 'value': 1}, 
                    {'field': 'B', 'value': 2}, 
                    {'field': 'B', 'value': 3},
                    {'field': 'B', 'value': 4},
                    {'field': 'PAYLOAD', 'value': b'xxx'}]


def test_convert_packet_in():
    """Test convert_packet_in method."""
    event = {
        'type': 'PACKET_IN',
        'msg': {
            '_pkt': [{'field': 'A', 'value': 1}],
            'data': '0102'
        }
    }
    Packet.zof_convert_packet_in(event)
    assert event['msg']['pkt'] == Packet(a=1, payload=b'\x01\x02')
    assert '_pkt' not in event['msg']
    assert 'data' not in event['msg']


def test_convert_packet_in_partial():
    """Test convert_packet_in method for incomplete event."""
    event = {
        'type': 'PACKET_IN',
        'msg': {
            'data': '0102'
        }
    }
    Packet.zof_convert_packet_in(event)
    assert event['msg']['pkt'] == Packet(payload=b'\x01\x02')
    assert 'data' not in event['msg']


def test_convert_packet_out():
    """Test convert__packet_out method."""
    event = {
        'type': 'PACKET_OUT',
        'msg': {
            'pkt': Packet(a=1, payload=b'\x01\x02')
        }
    }
    Packet.zof_convert_packet_out(event)
    assert event['msg']['_pkt'] == [{'field': 'A', 'value': 1}]
    assert event['msg']['_pkt_data'] == b'\x01\x02'
