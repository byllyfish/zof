from zoflite.datapath import Datapath
from mock_driver import MockDriver
import pytest


class MockController:	
	def __init__(self, loop=None):
		self.zof_loop = loop
		self.zof_driver = MockDriver()


def _make_dp():
	event = { 'type': 'CHANNEL_UP', 'datapath_id': '00:00:00:00:00:00:01'}
	return Datapath(MockController(), 1, event)


def test_datapath_repr():
	dp = _make_dp()
	assert repr(dp) == '<Datapath conn_id=1 dpid=00:00:00:00:00:00:01>'


def test_datapath_send():
	dp = _make_dp()
	dp.send({'type': 'FLOW_MOD'})


@pytest.mark.asyncio
async def test_datapath_request():
	dp = _make_dp()
	reply = await dp.request({'xid': 123, 'type': 'FLOW_MOD'})
	assert reply['xid'] == 123