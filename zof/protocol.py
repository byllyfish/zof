import asyncio


class Protocol(asyncio.SubprocessProtocol):
    buf = b''
    transport = None

    def __init__(self, post_event):
        self.post_event = post_event

    def connection_made(self, transport):
        self.transport = transport

    def connection_lost(self, exc):
        pass

    def pipe_data_received(self, fd, data):
        begin = 0
        offset = len(self.buf)
        self.buf += data
        while True:
            offset = self.buf.find(b'\x00', offset)
            if offset < 0:
                self.buf = self.buf[begin:]
                return
            self.post_event(self.buf[begin:offset])
            offset += 1
            begin = offset

    def process_exited(self):
        pass
