"""Test oftr api."""

from ipaddress import ip_address
import pytest

from zof import oftr


def test_zof_load_msg():
    """Test load_msg api."""
    assert oftr.zof_load_msg('{') is None
    assert oftr.zof_load_msg('{}') == {}


def test_zof_dump_msg():
    """Test dump_msg api."""
    event = {
        'info': [None, b'abc',
                 ip_address('127.0.0.1'),
                 ip_address('::1')]
    }
    expected = b'{"info": [null, "616263", "127.0.0.1", "::1"]}\x00'
    assert oftr.zof_dump_msg(event) == expected

    with pytest.raises(TypeError) as excinfo:
        oftr.zof_dump_msg(1 + 3j)

    assert 'is not JSON serializable' in str(excinfo.value)


@pytest.mark.asyncio
async def test_request_info(event_loop, caplog):
    """Test RequestInfo."""

    # pylint: disable=protected-access
    info = oftr._RequestInfo(event_loop, 1.0)
    info.handle_reply({})

    assert caplog.record_tuples == [('zof', 40, 'OFTR: Unexpected reply: {}')]
