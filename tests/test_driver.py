import pytest
import asyncio
from zoflite.driver import Driver
from zoflite.exception import RequestError


# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio

# Max size of RPC message supported by oftr.
MSG_LIMIT = 2**20 - 1


async def test_driver_request():
    """Driver context manager's request api."""

    async with Driver() as driver:
        assert driver.pid >= 0

        request = { 'id': 1, 'method': 'OFP.DESCRIPTION' }
        reply = await driver.request(request)

        assert request == { 'id': 1, 'method': 'OFP.DESCRIPTION' }, 'Request modified'
        assert reply['api_version'] == '0.9'
        assert reply['sw_desc'].startswith('0.')
        assert reply['versions'] == list(range(1, 7))


async def test_driver_dispatch():
    """Driver context manager with simple dispatcher."""

    incoming = []

    def _dispatch(_driver, event):
        incoming.append(event)

    async with Driver(_dispatch, True) as driver:
        assert driver.pid >= 0

    assert incoming == []


async def test_driver_not_reentrant():
    """Driver context manager is not re-entrant."""

    driver = Driver()
    async with driver:
        with pytest.raises(AssertionError):
            async with driver:
                pass


async def test_driver_nonexistant_method():
    """Non-existant JSON-RPC method."""

    async with Driver() as driver:
        request = { 'id': 1, 'method': 'NON_EXISTANT' }
        with pytest.raises(RequestError) as excinfo:
            reply = await driver.request(request)
        assert 'unknown method' in excinfo.value.message


async def test_driver_invalid_rpc():
    """Non-existant JSON-RPC method."""

    async with Driver() as driver:
        request = { 'id': 1, 'meth': 'INVALID' }
        with pytest.raises(RequestError) as excinfo:
            reply = await driver.request(request)
        assert 'missing required key \'method\'' in excinfo.value.message


async def test_large_rpc_too_big():
    """Large RPC payload (too big)."""

    incoming = []

    def _dispatch(_driver, event):
        incoming.append(event)

    async with Driver(_dispatch) as driver:
        request = { 'id': 1, 'method': 'FOO', 'params': 'x' * MSG_LIMIT }
        with pytest.raises(RequestError) as excinfo:
            await driver.request(request)

        # The reply error should be a closed error.
        assert 'connection closed' in excinfo.value.message

    assert incoming == []


async def test_large_rpc():
    """Large RPC payload (big, but not too big)."""

    incoming = []

    def _dispatch(_driver, event):
        incoming.append(event)

    async with Driver(_dispatch) as driver:
        request = { 'id': 1, 'method': 'FOO', 'params': 'x' * (MSG_LIMIT - 100) }
        with pytest.raises(RequestError) as excinfo:
            reply = await driver.request(request)

    assert 'unknown method' in excinfo.value.message
    assert incoming == []


async def _driver_request_benchmark(name, loops):
    """Benchmark making async requests."""

    from timeit import default_timer as _timer

    async def _test(loops):
        DESC = {'id': 1, 'method': 'OFP.DESCRIPTION'}
        async with Driver() as driver:
            start_time = _timer()
            for _ in range(loops):
                await driver.request(DESC)
            return _timer() - start_time

    bench = { 'benchmark': name, 'loops': loops, 'times': [] }

    for _ in range(4):
        bench['times'].append(await _test(bench['loops']))

    return bench


async def test_driver_request_benchmark():
    """Benchmark making async requests."""

    print(await _driver_request_benchmark('driver_request', 1000))


async def test_driver_openflow():
    """Connect agent driver to controller driver."""

    controller_log = []
    agent_log = []

    def _handle_controller(_driver, event):
        controller_log.append(event['type'])

    def _handle_agent(_driver, event):
        agent_log.append(event['type'])

    async with Driver(_handle_controller) as controller:
        # Start controller listening on a port.
        await controller.listen('6653')

        async with Driver(_handle_agent) as agent:
            # Agent connects to controller.
            conn_id = await agent.connect('127.0.0.1:6653')
            agent.send(dict(type='BARRIER_REPLY', conn_id=conn_id))
            await agent.close(conn_id)

    assert controller_log == ['CHANNEL_UP', 'BARRIER_REPLY', 'CHANNEL_DOWN']
    assert agent_log == ['CHANNEL_UP', 'CHANNEL_DOWN']
