import asyncio
import time
from unittest import skipIf
from zof.connection import Connection
from .asynctestcase import AsyncTestCase

# Max message size is 1MB.
MSG_LIMIT = 2**20

# Skip tests that send big messages.
SKIP_BIG_MESSAGES = False

# Pass these args when launching oftr.
OFTR_ARGS = ''  # '--trace=rpc,msg --loglevel=debug'


class ConnectionTestCase(AsyncTestCase):
    async def setUp(self):
        oftr_options = {'args': OFTR_ARGS}
        self.conn = Connection(oftr_options=oftr_options)
        await self.conn.connect()

    async def tearDown(self):
        self.conn.close()
        return_code = await self.conn.disconnect()
        if return_code:
            raise Exception('oftr exited with return code %d' % return_code)

    # Basic tests.

    async def test_rpc(self):
        # If we write a valid JSON-RPC method, we should get a result back.
        msg = b'{"id":1234,"method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result, b'{"id":1234,"result":{"api_version":"0.9","sw_desc":')

    async def test_rpc_no_id(self):
        # If we write a valid JSON-RPC method with no id, there should be no response.
        msg = b'{"method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        with self.assertRaises(asyncio.TimeoutError):
            result = await asyncio.wait_for(self.conn.readline(), 1.0)
            self.assertIsNone(result)

    async def test_rpc_send_no_datapath(self):
        # If we write a valid JSON-RPC OFP.SEND method, there should be a response.
        msg = b'{"id":7,"method":"OFP.SEND","params":{"version":4,"type":"FEATURES_REQUEST"}}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result,
            b'{"id":7,"error":{"code":-65000,"message":"YAML:1:39: error: unable to locate connection; no conn_id or datapath_id'
        )

    async def test_rpc_send_no_id_datapath(self):
        msg = b'{"method":"OFP.SEND","params":{"version":4,"type":"FEATURES_REQUEST","xid":12}}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertRegex(
            result,
            b'{"method":"OFP.MESSAGE","params":{"type":"CHANNEL_ALERT","time":"[0-9.]+","conn_id":0,"datapath_id":"","xid":12,'
        )

    async def test_rpc_send_missing_datapath(self):
        # If we write a valid JSON-RPC OFP.SEND method, there should be a response.
        msg = b'{"id":8,"method":"OFP.SEND","params":{"datapath_id":"00:00:00:00:00:00:00:01","type":"FEATURES_REQUEST"}}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result,
            b'{"id":8,"error":{"code":-65000,"message":"YAML:1:39: error: unable to locate datapath_id 00:00:00:00:00:00:00:01'
        )

    async def test_rpc_hex_id(self):
        # If we write a valid JSON-RPC method with a hexadecimal ID, we should
        # get a result back.
        msg = b'{"id":"0x1234","method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result, b'{"id":4660,"result":{"api_version":"0.9","sw_desc":')

    # Test the connection transport limits.

    async def test_short_malformed(self):
        # Write a short malformed json message.
        self.conn.write(b'hello')
        result = await self.conn.readline()
        self.assertEqual(
            result,
            b'{"id":null,"error":{"code":-32600,"message":"YAML:1:1: error: not a mapping\\nhello\\n^~~~~"}}'
        )
        await self._still_alive()

    @skipIf(SKIP_BIG_MESSAGES, "skipping big message tests")
    async def test_write_max_size(self):
        # Write a maximum sized message.
        junk = b'x' * (MSG_LIMIT - 1)
        self.conn.write(junk)
        result = await self.conn.readline()
        self.assert_prefix(
            result,
            b'{"id":null,"error":{"code":-32600,"message":"YAML:1:1: error: not a mapping\\nxxx'
        )
        await self._still_alive()

    @skipIf(SKIP_BIG_MESSAGES, "skipping big message tests")
    async def test_write_too_big(self):
        # Write a message that is too big.
        junk = b'x' * MSG_LIMIT
        self.conn.write(junk)

        # We should receive a message that the RPC request is too big.
        result = await self.conn.readline()
        self.assertEqual(
            result,
            b'{"id":null,"error":{"code":-32600,"message":"RPC request is too big"}}'
        )
        await self._end_of_input()

    @skipIf(SKIP_BIG_MESSAGES, "skipping big message tests")
    async def test_zmassive_write(self):
        # Now, write enough messages to really back things up.
        count = 5
        junk = b'z' * (MSG_LIMIT - 1)

        for _ in range(count):
            self.conn.write(junk)

        t = time.perf_counter()
        await self.conn.drain()
        t = time.perf_counter() - t
        print('drain time elapsed', t)

        for _ in range(count):
            result = await self.conn.readline()
            self.assert_prefix(
                result,
                b'{"id":null,"error":{"code":-32600,"message":"YAML:1:1: error: not a mapping\\nzzz'
            )

        await self._still_alive()

    # Test invalid input.

    async def test_rpc_invalid_json(self):
        # If we write an invalid message, we should get back an error with a
        # id=null.
        msg = b'{invalid'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(result,
                           b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    async def test_rpc_incorrect_jsonrpc_version(self):
        # If we write a message with an incorrect jsonrpc version, we should
        # get back an error.
        msg = b'{"jsonrpc":"3.0","id":"13","method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result,
            b'{"id":13,"error":{"code":-32600,"message":"YAML:1:2: error: Unsupported jsonrpc version'
        )
        await self._still_alive()

    async def test_rpc_invalid_id(self):
        msg = b'{"id":"abc","method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result,
            b'{"id":null,"error":{"code":-32600,"message":"YAML:1:7: error: Invalid RPC ID'
        )
        await self._still_alive()

    async def test_rpc_id_null(self):
        # If we write a message with a null id, it is treated as a valid id.
        msg = b'{"id":null,"method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(result, b'{"id":null,"result":{"api_version":')
        await self._still_alive()

    async def test_rpc_id_too_big(self):
        for id_val in [2**64 - 2, 2**64 - 1, 2**64, 2**64 + 1]:
            msg = b'{"id":%d,"method":"OFP.DESCRIPTION"}' % id_val
            self.conn.write(msg)
            result = await self.conn.readline()
            self.assert_prefix(
                result,
                b'{"id":null,"error":{"code":-32600,"message":"YAML:1:7: error: Invalid RPC ID'
            )
            await self._still_alive()

    async def test_rpc_id_max(self):
        id_val = 2**64 - 3
        msg = b'{"id":%d,"method":"OFP.DESCRIPTION"}' % id_val
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(result,
                           b'{"id":%d,"result":{"api_version":' % id_val)
        await self._still_alive()

    async def test_ofp_send_invalid(self):
        # If we write an invalid OFP.SEND message, we should get back an error.
        msg = b'{"id":321,"method":"OFP.SEND","params":{"type":"foo"}}'
        self.conn.write(msg)
        result = await asyncio.wait_for(self.conn.readline(), 1.0)
        self.assert_prefix(
            result,
            b'{"id":321,"error":{"code":-32600,"message":"YAML:1:48: error: unknown value \\"foo\\" Did you mean \\"HELLO\\"?'
        )
        await self._still_alive()

    async def test_ofp_send_invalid_no_id(self):
        # If we write an invalid OFP.SEND message with no id, we should get back
        # a OFP.MESSAGE notification.
        msg = b'{"method":"OFP.SEND","params":{"type":"foo","xid":133}}'
        self.conn.write(msg)
        result = await asyncio.wait_for(self.conn.readline(), 1.0)
        self.assertRegex(
            result,
            b'{"method":"OFP.MESSAGE","params":{"type":"CHANNEL_ALERT","time":"[0-9.]+","conn_id":0,"datapath_id":"","xid":133,'
        )
        await self._still_alive()

    async def test_ofp_send_invalid_no_alert(self):
        # If we write an invalid OFP.SEND message for a non-existant datapath
        # with 'NO_ALERT' specified, we should not get a response back.
        msg = b'{"method":"OFP.SEND","params":{"datapath_id":"0x01","type":"FEATURES_REQUEST","xid":134,"flags":["NO_ALERT"]}}'
        self.conn.write(msg)
        with self.assertRaises(asyncio.TimeoutError):
            result = await asyncio.wait_for(self.conn.readline(), 1.0)
            self.assertIsNone(result)

    # The following tests are taken from http://www.jsonrpc.org/specification

    async def test_rpc_call_of_nonexistant_method(self):
        msg = b'{"jsonrpc": "2.0", "method": "foobar", "id": "1"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(
            result,
            b'{"id":1,"error":{"code":-32601,"message":"YAML:1:30: error: unknown method'
        )
        await self._still_alive()

    async def test_rpc_call_with_invalid_json(self):
        msg = b'{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(result,
                           b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    async def test_rpc_call_with_invalid_request_object(self):
        msg = b'{"jsonrpc": "2.0", "method": 1, "params": "bar"}'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(result,
                           b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    async def test_rpc_call_with_invalid_batch(self):
        msg = b'[1,2,3]'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assert_prefix(result,
                           b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    # Test close(write=True)

    async def test_close_write(self):
        self.conn.write(b'{"id":12300,"method":"OFP.DESCRIPTION"}')
        self.conn.close(write=True)
        result = await self.conn.readline()
        self.assert_prefix(result, b'{"id":12300,"result":{"api_version":')
        await self._end_of_input()

    async def test_close_incomplete_write(self):
        self.conn.write(
            b'{"id":12300,"method":"OFP.DESCRIPTION"}', delimiter=None)
        self.conn.close(write=True)
        result = await self.conn.readline()
        self.assert_prefix(result, b'')
        await self._end_of_input()

    # Helper methods

    async def _end_of_input(self):
        result = await self.conn.readline()
        self.assertEqual(result, b'')

    async def _still_alive(self):
        self.conn.write(b'{"id":12300,"method":"OFP.DESCRIPTION"}')
        result = await self.conn.readline()
        self.assert_prefix(result, b'{"id":12300,"result":{"api_version":')

    def assert_prefix(self, value, prefix):
        if not value.startswith(prefix):
            self.fail('Prefix %s does not match: %s' % (prefix, value))
