import asyncio
import json
import os
import re
import signal
import tempfile
import zof

#       zof <---------+
#         |           |
#      exabgp         |
#         |           |
#     bgp_tunnel -----+

APP = zof.Application('bgp')


class BGPNeighbor:
    """Represents a peer connection to a BGP neighbor."""

    EXABGP_CONF = b'''
        neighbor %(peer_address)a {
            router-id %(router_id)a;
            local-as %(local_as)a;
            local-address %(local_address)a;
            peer-as %(peer_as)a;
            api {
                processes [tunnel];
                neighbor-changes;
                receive { 
                    open;
                    update;
                    parsed;
                }
            }
        }
    '''

    def __init__(self, local_as, local_address, router_id, peer_as, peer_address):
        self.local_as = local_as
        self.local_address = local_address
        self.router_id = router_id
        self.peer_as = peer_as
        self.peer_address = peer_address

    def conf(self):
        return self.EXABGP_CONF % {
            b'local_as': self.local_as,
            b'local_address': self.local_address,
            b'router_id': self.router_id,
            b'peer_as': self.peer_as,
            b'peer_address': self.peer_address
        }


class BGPServer:
    """BGP Server implemented using exabgp."""

    EXABGP_CONF = b'''
        process tunnel {
          run /usr/bin/nc -U %(server_path)a;
          encoder json;
        }

        %(neighbor_conf)b
    '''

    EXABGP_ENV = b'''
        [exabgp.api]
        cli = false
        [exabgp.tcp]
        bind = %(tcp_bind)a
        port = %(tcp_port)d  
    '''

    def __init__(self):
        self.server_path = os.path.join(os.path.dirname(__file__), 'zof_bgp.sock')
        self.server = None
        self.proc = None
        self.exabgp_conf = tempfile.NamedTemporaryFile()
        self.exabgp_env = tempfile.NamedTemporaryFile()
        self.neighbors = []
        APP.logger.info('BGPServer path=%s', self.server_path)

    def __del__(self):
        self.exabgp_conf.close()
        self.exabgp_env.close()

    def add_neighbor(self, local_as, local_address, router_id, peer_as, peer_address):
        """Add BGP neighbor."""
        neighbor = BGPNeighbor(local_as, local_address, router_id, peer_as, peer_address)
        self.neighbors.append(neighbor)
        self._write_conf()
        self._reload_conf()
        return neighbor

    async def start(self):
        """Start BGP server."""
        assert self.server is None
        self.server = await asyncio.start_unix_server(self._accept, path=self.server_path)
        await self._run_exabgp()

    async def stop(self):
        """Stop BGP server."""
        if self.server is None:
            return
        self.server.close()
        try:
            self.proc.terminate()
        except ProcessLookupError:
            pass

    async def _accept(self, reader, _writer):
        """Read from connection to exabgp tunnel and post BGP events."""
        while True:
            line = await reader.readline()
            if not line:
                break
            message = self._decode_message(line)
            if message:
                zof.post_event(message)

    def _decode_message(self, line):
        """Decode JSON message from exabgp."""
        try:
            line = _fix_exabgp_line(line)
            message = json.loads(line)
            assert 'event' not in message
            message['event'] = 'BGP'
            APP.logger.info(repr(message))
            return message         
        except json.decoder.JSONDecodeError:
            APP.logger.error("JSON error: %s", line)
            return None

    async def _run_exabgp(self):
        """Run exabgp with tunnel subprocess."""
        self._write_conf()
        self._write_env()
        args = ['exabgp', '-e', self.exabgp_env.name, self.exabgp_conf.name]
        self.proc = await asyncio.create_subprocess_exec(*args)

    def _write_conf(self):
        """Construct temporary file with exabgp config."""
        neighbor_conf = b'\n'.join(neigh.conf() for neigh in self.neighbors)
        self.exabgp_conf.truncate(0)
        self.exabgp_conf.write(self.EXABGP_CONF % {
            b'server_path': self.server_path,
            b'neighbor_conf': neighbor_conf})
        self.exabgp_conf.flush()

    def _write_env(self, tcp_bind='127.0.0.1', tcp_port=1790):
        """Construct temporary file with exabgp envionment variables."""
        self.exabgp_env.write(self.EXABGP_ENV % {
            b'tcp_bind': tcp_bind,
            b'tcp_port': tcp_port})
        self.exabgp_env.flush()

    def _reload_conf(self):
        """Signal exabgp to reload its config."""
        APP.logger.info('sending signal...')
        #self.proc.send_signal(signal.SIGUSR1)


FIX_REGEX = re.compile(br'"reason": (peer reset, message \[[^\]]+\] error\[[^\]]+\])')

def _fix_exabgp_line(line):
    return FIX_REGEX.sub(br'"reason": "\1"', line)


@APP.event('start')
async def start(_):
    APP.server = BGPServer()
    await APP.server.start()
    neigh = APP.server.add_neighbor(1, '127.0.0.1', '1.1.1.1', 2, '127.0.0.1')


@APP.event('stop')
async def stop(_):
    await APP.server.stop()


if __name__ == '__main__':
    zof.run()
