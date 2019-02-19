"""Test oftr api."""

import pytest
from unittest.mock import MagicMock, call

from zof import oftr


def test_zof_load_msg():
    """Test load_msg api."""
    assert oftr.zof_load_msg('{') is None
    assert oftr.zof_load_msg(b'{}') == {}


def test_zof_dump_msg():
    """Test dump_msg api."""
    event = {'info': [None, 'abc']}
    expected = b'{"info":[null,"abc"]}'
    assert oftr.zof_dump_msg(event) == expected

    with pytest.raises(TypeError) as excinfo:
        oftr.zof_dump_msg(b'abc')

    assert 'is not JSON serializable' in str(excinfo.value)


@pytest.mark.asyncio
async def test_request_info(event_loop, caplog):
    """Test RequestInfo with invalid reply."""

    # pylint: disable=protected-access
    info = oftr._RequestInfo(event_loop, 1.0)
    assert info.handle_reply({})

    assert caplog.record_tuples == [('zof', 40, 'OFTR: Unexpected reply: {}')]


@pytest.mark.asyncio
async def test_request_info_multipart(event_loop, caplog):
    """Test RequestInfo with multipart reply."""

    # pylint: disable=protected-access
    info = oftr._RequestInfo(event_loop, 1.0)
    assert not info.handle_reply({
        'type': 'FOO',
        'flags': ['MORE'],
        'msg': [1]
    })
    assert not info.handle_reply({
        'type': 'FOO',
        'flags': ['MORE'],
        'msg': [2]
    })
    assert info.handle_reply({'type': 'FOO', 'msg': [3]})

    assert info.multipart_reply == {
        'type': 'FOO',
        'flags': ['MORE'],
        'msg': [1, 2, 3]
    }
    assert not caplog.record_tuples


@pytest.mark.asyncio
async def test_request_info_multipart_inconsistent(event_loop, caplog):
    """Test RequestInfo with inconsistent multipart reply."""

    # pylint: disable=protected-access
    info = oftr._RequestInfo(event_loop, 1.0)
    assert not info.handle_reply({
        'type': 'FOO',
        'flags': ['MORE'],
        'msg': [1]
    })
    assert not info.handle_reply({
        'type': 'BAR',
        'flags': ['MORE'],
        'msg': [2]
    })
    assert info.handle_reply({'type': 'FOO', 'msg': [3]})

    assert info.multipart_reply == {
        'type': 'FOO',
        'flags': ['MORE'],
        'msg': [1, 3]
    }
    assert caplog.record_tuples == [
        ('zof', 30, 'Inconsistent multipart type: BAR (expected FOO)')
    ]


def test_oftr_protocol_data_received():
    """Test OftrProtocol's data_received method."""

    protocol = oftr.OftrProtocol(None, None)
    protocol.msg_received = MagicMock(return_value=None)
    protocol.msg_failure = MagicMock(return_value=None)

    # Empty buffer.
    protocol.data_received(b'')
    protocol.msg_received.assert_not_called()

    # Exact buffer size.
    protocol.data_received(b'\x00\x00\x03\xF5[1]')
    protocol.msg_received.assert_called_once_with([1])
    protocol.msg_received.reset_mock()

    # Undersized buffer.
    for ch in b'\x00\x00\x03\xF5[2':
        protocol.data_received(bytes([ch]))
        protocol.msg_received.assert_not_called()
    protocol.data_received(b']')
    protocol.msg_received.assert_called_once_with([2])
    protocol.msg_received.reset_mock()

    # Two messages in buffer. Exact buffer size.
    protocol.data_received(b'\x00\x00\x01\xF53\x00\x00\x01\xF54')
    protocol.msg_received.assert_has_calls([call(3), call(4)])
    protocol.msg_received.reset_mock()

    # Two messages, first oversized, second undersized.
    protocol.data_received(b'\x00\x00\x01\xF55\x00')
    for ch in b'\x00\x01\xF56':
        protocol.data_received(bytes([ch]))
    protocol.msg_received.assert_has_calls([call(5), call(6)])
    protocol.msg_received.reset_mock()

    # No failures.
    protocol.msg_failure.assert_not_called()

    # Force a failure.
    protocol.data_received(b'\x00\x00\x01\xF47')
    protocol.msg_received.assert_not_called()
    protocol.msg_failure.assert_called_once_with(b'\x00\x00\x01\xF47')
