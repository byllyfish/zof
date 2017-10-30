import asyncio
from zof.event import load_event


class Protocol(asyncio.SubprocessProtocol):
    """Implements an asyncio Protocol for parsing data received from oftr.
    """

    def __init__(self, post_event):
        self.post_event = post_event
        self.buf = b''
        self.exit_future = asyncio.Future()

    def pipe_data_received(self, fd, data):
        begin = 0
        offset = len(self.buf)
        self.buf += data
        while True:
            offset = self.buf.find(b'\x00', offset)
            if offset < 0:
                self.buf = self.buf[begin:]
                return
            if begin != offset:
                self.post_event(load_event(self.buf[begin:offset]))
            offset += 1
            begin = offset

    def process_exited(self):
        self.exit_future.set_result(0)
