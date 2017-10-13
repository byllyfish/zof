import unittest 
from zof.protocol import Protocol


class MockController:
    events = []

    def post_event(self, event):
        self.events.append(event)


class ProtocolTestCase(unittest.TestCase):

    def test_data_received(self):
        controller = MockController()
        proto = Protocol(controller.post_event)
        proto.pipe_data_received(None, b'1\x002\x00')
        self.assertEqual(controller.events, [b'1', b'2'])
        self.assertEqual(proto.buf, b'')
        proto.pipe_data_received(None, b'')
        proto.pipe_data_received(None, b'3')
        proto.pipe_data_received(None, b'3')
        self.assertEqual(controller.events, [b'1', b'2'])
        self.assertEqual(proto.buf, b'33')
        proto.pipe_data_received(None, b'\x00')
        self.assertEqual(controller.events, [b'1', b'2', b'33'])
        self.assertEqual(proto.buf, b'')
        proto.pipe_data_received(None, b'\x00\x00')
        self.assertEqual(controller.events, [b'1', b'2', b'33', b'', b''])
        self.assertEqual(proto.buf, b'')
        proto.pipe_data_received(None, b'\n')
        self.assertEqual(controller.events, [b'1', b'2', b'33', b'', b''])
        self.assertEqual(proto.buf, b'\n')
        proto.pipe_data_received(None, b'x\x00')
        self.assertEqual(controller.events, [b'1', b'2', b'33', b'', b'', b'\nx'])
        self.assertEqual(proto.buf, b'')
