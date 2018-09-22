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
    return Datapath(MockController(), 1, '00:00:00:00:00:00:01')


def test_datapath_repr():
    dp = _make_dp()
    assert repr(dp) == '<Datapath conn_id=1 dpid=00:00:00:00:00:00:01>'


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