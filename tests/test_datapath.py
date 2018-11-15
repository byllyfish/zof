"""Test zof.Datapath class."""

import pytest

from mock_driver import MockDriver
from zof.datapath import Datapath
from zof.packet import Packet
from zof import RequestError


class MockController:
    """Mock controler for testing datapath."""

    def __init__(self, loop=None):
        self.zof_loop = loop
        self.zof_driver = MockDriver()

    def on_exception(self, exc):
        print('exception: %r' % exc)


def _make_dp():
    return Datapath(MockController(), 1, 1)


def test_datapath_repr():
    dp = _make_dp()
    assert repr(dp) == '<Datapath conn_id=1 dp_id=1>'


def test_datapath_send():
    event = {
        'type': 'PACKET_OUT',
        'msg': {
            'pkt': Packet(a=1, payload=b'\x01\x02')
        }
    }
    _make_dp().send(event)
    assert event == {
        'conn_id': 1,
        'type': 'PACKET_OUT',
        'msg': {
            '_pkt': [{
                'field': 'A',
                'value': 1
            }],
            '_pkt_data': b'\x01\x02'
        }
    }


@pytest.mark.asyncio
async def test_datapath_request():
    dp = _make_dp()
    reply = await dp.request({'xid': 123, 'type': 'FLOW_MOD'})
    assert reply['xid'] == 123


@pytest.mark.asyncio
async def test_datapath_close():
    dp = _make_dp()
    assert not dp.closed
    dp.close()
    assert dp.closed

    with pytest.raises(RequestError):
        dp.send({'type': 'BARRIER_REQUEST'})

    with pytest.raises(RequestError):
        await dp.request({'type': 'BARRIER_REQUEST'})


def test_datapath_ports():
    """Test handling of CHANNEL_UP and PORT_STATUS events."""
    dp = _make_dp()

    channel_up = {
        'type': 'CHANNEL_UP',
        'msg': {
            'features': {
                'ports': [
                    {'port_no': 1},
                    {'port_no': 2},
                    {'port_no': 'LOCAL'}
                ]
            }
        }
    }
    dp.zof_from_channel_up(channel_up)

    assert dp.ports == {
        1: {'port_no': 1},
        2: {'port_no': 2},
        'LOCAL': {'port_no': 'LOCAL'}
    }

    port_status = {
        'type': 'PORT_STATUS',
        'msg': {
            'port_no': 2,
            'reason': 'DELETE'
        }
    }
    dp.zof_from_port_status(port_status)

    assert dp.ports == {
        1: {'port_no': 1},
        'LOCAL': {'port_no': 'LOCAL'}
    }

    port_status = {
        'type': 'PORT_STATUS',
        'msg': {
            'port_no': 3,
            'reason': 'ADD'
        }
    }
    dp.zof_from_port_status(port_status)

    assert dp.ports == {
        1: {'port_no': 1},
        'LOCAL': {'port_no': 'LOCAL'},
        3: {'port_no': 3, 'reason': 'ADD'}
    }
