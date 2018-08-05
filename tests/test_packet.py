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
    pkt = Packet.from_field_list(data)
    assert pkt.a == 1
    assert pkt.b == [2, 3, 4]
    assert pkt.payload == b'xxx'


def test_packet_to_field_list():
    """Test to_field_list factory method."""
    pkt = Packet(a=1, b=[2, 3, 4], payload=b'xxx')
    data = pkt.to_field_list()
    assert data == [{'field': 'A', 'value': 1}, 
                    {'field': 'B', 'value': 2}, 
                    {'field': 'B', 'value': 3},
                    {'field': 'B', 'value': 4},
                    {'field': 'PAYLOAD', 'value': b'xxx'}]


