import unittest
import asyncio
import time
from pylibofp.connection import Connection

# Max message size is 1MB.
MSG_LIMIT = 2**20

# Test timeout in seconds
TIMEOUT = 8.0

# Skip tests that send big messages.
SKIP_BIG_MESSAGES = False

# Pass these args when launching libofp.
LIBOFP_ARGS = [] #['--trace=rpc,msg', '--loglevel=debug']


# Method decorator for async tests.
def run_async(func):
    def async_test_wrapper(self):
        task = asyncio.wait_for(func(self), TIMEOUT)
        ConnectionTestCase.loop.run_until_complete(task)
    return async_test_wrapper


class ConnectionTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()

    @run_async
    async def setUp(self):
        self.conn = Connection(libofp_args=LIBOFP_ARGS)
        await self.conn.connect()

    @run_async
    async def tearDown(self):
        self.conn.close()
        await self.conn.disconnect()

    # Basic tests.

    @run_async
    async def test_rpc(self):
        # If we write a valid JSON-RPC method, we should get a result back.
        msg = b'{"id":1234,"method":"OFP.DESCRIPTION"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":1234,"result":{"major_version":0,"minor_version":1,"software_version":')

    @run_async
    async def test_rpc_no_id(self):
        # If we write a valid JSON-RPC method with no id, there should be no response.
        msg = b'{"method":"OFP.DESCRIPTION"}\n'
        self.conn.write(msg)
        with self.assertRaises(asyncio.TimeoutError):
            result = await asyncio.wait_for(self.conn.readline(), 1.0)
            self.assertIsNone(result)

    @run_async
    async def test_rpc_send_no_datapath(self):
        # If we write a valid JSON-RPC OFP.SEND method, there should be a response.
        msg = b'{"id":7,"method":"OFP.SEND","params":{"version":4,"type":"FEATURES_REQUEST"}}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":7,"error":{"code":-65000,"message":"YAML:1:39: error: unable to locate connection; no datapath_id or conn_id')

    @run_async
    async def test_rpc_send_no_id_datapath(self):
        msg = b'{"method":"OFP.SEND","params":{"version":4,"type":"FEATURES_REQUEST","xid":12}}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"method":"OFP.ALERT","params":{"conn_id":0,"datapath_id":"","xid":12,"time":')

    @run_async
    async def test_rpc_send_missing_datapath(self):
        # If we write a valid JSON-RPC OFP.SEND method, there should be a response.
        msg = b'{"id":8,"method":"OFP.SEND","params":{"datapath_id":"00:00:00:00:00:00:00:01","type":"FEATURES_REQUEST"}}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":8,"error":{"code":-65000,"message":"YAML:1:39: error: unable to locate datapath_id 00:00:00:00:00:00:00:01')

    @run_async
    async def test_rpc_hex_id(self):
        # If we write a valid JSON-RPC method with a hexadecimal ID, we should 
        # get a result back.
        msg = b'{"id":"0x1234","method":"OFP.DESCRIPTION"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":4660,"result":{"major_version":0,"minor_version":1,"software_version":')

    # Test the connection transport limits.

    @run_async
    async def test_short_malformed(self):
        # Write a short malformed json message.
        self.conn.write(b'hello\n')
        result = await self.conn.readline()
        self.assertEqual(result, b'{"id":null,"error":{"code":-32600,"message":"YAML:1:1: error: not a mapping\\nhello\\n^~~~~"}}\n')
        await self._still_alive()

    @unittest.skipIf(SKIP_BIG_MESSAGES, "skipping big message tests")
    @run_async
    async def test_write_max_size(self):
        # Write a maximum sized message.
        junk = b'x' * (MSG_LIMIT - 1) + b'\n'
        self.conn.write(junk)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":"YAML:1:1: error: not a mapping\\nxxx')
        await self._still_alive()

    @unittest.skipIf(SKIP_BIG_MESSAGES, "skipping big message tests")
    @run_async
    async def test_write_too_big(self):
        # Write a message that is too big.
        junk = b'x' * MSG_LIMIT + b'\n'
        self.conn.write(junk)

        # We should receive a message that the RPC request is too big.
        result = await self.conn.readline()
        self.assertEqual(result, b'{"id":null,"error":{"code":-32600,"message":"RPC request is too big"}}\n')
        await self._end_of_input()

    @unittest.skipIf(SKIP_BIG_MESSAGES, "skipping big message tests")
    @run_async
    async def test_massive_write(self):
        # Now, write enough messages to really back things up.
        count = 5
        junk = b'z' * (MSG_LIMIT - 1) + b'\n'

        for _ in range(count):
            self.conn.write(junk)

        t = time.perf_counter()
        await self.conn.drain()
        t = time.perf_counter() - t
        print('drain time elapsed', t)

        for _ in range(count):
            result = await self.conn.readline()
            self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":"YAML:1:1: error: not a mapping\\nzzz')

        await self._still_alive()

    # Test invalid input.

    @run_async
    async def test_rpc_invalid_json(self):
        # If we write an invalid message, we should get back an error with a 
        # id=null.
        msg = b'{invalid\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    @run_async
    async def test_rpc_incorrect_jsonrpc_version(self):
        # If we write a message with an incorrect jsonrpc version, we should
        # get back an error.
        msg = b'{"jsonrpc":"3.0","id":"13","method":"OFP.DESCRIPTION"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":13,"error":{"code":-32600,"message":"YAML:1:2: error: Unsupported jsonrpc version')
        await self._still_alive()

    @run_async
    async def test_rpc_invalid_id(self):
        msg = b'{"id":"abc","method":"OFP.DESCRIPTION"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":"YAML:1:7: error: Invalid RPC ID')
        await self._still_alive()

    @run_async
    async def test_rpc_id_null(self):
        # If we write a message with a null id, it is treated as a valid id.
        msg = b'{"id":null,"method":"OFP.DESCRIPTION"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"result":{"major_version":')
        await self._still_alive()

    @run_async
    async def test_rpc_id_too_big(self):
        for id_val in [2**64-2, 2**64-1, 2**64, 2**64+1]:
            msg = b'{"id":%d,"method":"OFP.DESCRIPTION"}\n' % id_val
            self.conn.write(msg)
            result = await self.conn.readline()
            self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":"YAML:1:7: error: Invalid RPC ID')
            await self._still_alive()

    @run_async
    async def test_rpc_id_max(self):
        id_val = 2**64-3
        msg = b'{"id":%d,"method":"OFP.DESCRIPTION"}\n' % id_val
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":%d,"result":{"major_version":' % id_val)
        await self._still_alive()

    @run_async
    async def test_ofp_send_invalid(self):
        # If we write an invalid OFP.SEND message, we should get back an error.
        msg = b'{"id":321,"method":"OFP.SEND","params":{"type":"foo"}}\n'
        self.conn.write(msg)
        result = await asyncio.wait_for(self.conn.readline(), 1.0)
        self.assertPrefix(result, b'{"id":321,"error":{"code":-32600,"message":"YAML:1:48: error: unknown value \\"foo\\" Did you mean \\"HELLO\\"?')
        await self._still_alive()

    @run_async
    async def test_ofp_send_invalid_no_id(self):
        # If we write an invalid OFP.SEND message with no id, we should get back
        # a OFP.ALERT notification.
        msg = b'{"method":"OFP.SEND","params":{"type":"foo","xid":133}}\n'
        self.conn.write(msg)
        result = await asyncio.wait_for(self.conn.readline(), 1.0)
        self.assertPrefix(result, b'{"method":"OFP.ALERT","params":{"conn_id":0,"datapath_id":"","xid":133,"time":')
        await self._still_alive()

    # The following tests are taken from http://www.jsonrpc.org/specification
    
    @run_async
    async def test_rpc_call_of_nonexistant_method(self):
        msg = b'{"jsonrpc": "2.0", "method": "foobar", "id": "1"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":1,"error":{"code":-32601,"message":"YAML:1:30: error: unknown method')
        await self._still_alive()

    @run_async
    async def test_rpc_call_with_invalid_json(self):
        msg = b'{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    @run_async
    async def test_rpc_call_with_invalid_request_object(self):
        msg = b'{"jsonrpc": "2.0", "method": 1, "params": "bar"}\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    @run_async
    async def test_rpc_call_with_invalid_batch(self):
        msg = b'[1,2,3]\n'
        self.conn.write(msg)
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":null,"error":{"code":-32600,"message":')
        await self._still_alive()

    # Helper methods

    async def _end_of_input(self):
        result = await self.conn.readline()
        self.assertEqual(result, b'')

    async def _still_alive(self):
        self.conn.write(b'{"id":12300,"method":"OFP.DESCRIPTION"}\n')
        result = await self.conn.readline()
        self.assertPrefix(result, b'{"id":12300,"result":{"major_version":')

    def assertPrefix(self, value, prefix):
        if not value.startswith(prefix):
            self.fail('Prefix %s does not match: %s' % (prefix, value))

