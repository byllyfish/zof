import unittest
import asyncio
from zof.protocol import Protocol
from zof.connection import Connection
from .asynctestcase import AsyncTestCase


class MockController:
    def __init__(self):
        self.events = []

    def post_event(self, event):
        self.events.append(event)


class ProtocolTestCase(unittest.TestCase):
    def test_data_received(self):
        controller = MockController()
        proto = Protocol(controller.post_event)
        proto.pipe_data_received(None, b'1\x002\x00')
        self.assertEqual(controller.events, [1, 2])
        self.assertEqual(proto.buf, b'')
        proto.pipe_data_received(None, b'')
        proto.pipe_data_received(None, b'3')
        proto.pipe_data_received(None, b'3')
        self.assertEqual(controller.events, [1, 2])
        self.assertEqual(proto.buf, b'33')
        proto.pipe_data_received(None, b'\x00')
        self.assertEqual(controller.events, [1, 2, 33])
        self.assertEqual(proto.buf, b'')
        proto.pipe_data_received(None, b'\x00\x00')
        self.assertEqual(controller.events, [1, 2, 33])
        self.assertEqual(proto.buf, b'')
        proto.pipe_data_received(None, b'"y')
        self.assertEqual(controller.events, [1, 2, 33])
        self.assertEqual(proto.buf, b'"y')
        proto.pipe_data_received(None, b'x"\x00')
        self.assertEqual(controller.events, [1, 2, 33, 'yx'])
        self.assertEqual(proto.buf, b'')


# Pass these args when launching oftr.
OFTR_ARGS = ''  # '--trace=rpc,msg --loglevel=debug'


class ProtocolConnectionTestCase(AsyncTestCase):
    async def setUp(self):
        oftr_options = {'args': OFTR_ARGS}
        self.conn = Connection(oftr_options=oftr_options)
        self.controller = MockController()
        await self.conn.connect(self.controller.post_event)
        assert self.conn.pid > 0

    async def tearDown(self):
        self.conn.close(True)
        return_code = await self.conn.disconnect()
        if return_code:
            raise Exception('oftr exited with return code %d' % return_code)

    async def test_rpc(self):
        # If we write a valid JSON-RPC method, we should get a result back.
        msg = b'{"id":1234,"method":"OFP.DESCRIPTION"}'
        self.conn.write(msg)
        for _ in range(10):
            await asyncio.sleep(0.01)
            if self.controller.events:
                break
        result = self.controller.events[0]
        self.assertEqual(result['id'], 1234)
        self.assertEqual(result['result']['api_version'], '0.9')
