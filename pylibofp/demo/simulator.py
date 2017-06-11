import argparse
import asyncio

from ofp_app import ofp_app, ofp_run, ofp_compile, ofp_default_args
from ofp_app.ofp_args import import_module


class Simulator(object):
    def __init__(self, datapath_id):
        self.datapath_id = datapath_id
        app.sims.append(self)

    async def start(self):
        conn_id = await app.connect('127.0.0.1:6653', versions=[1])
        app.conn_to_sim[conn_id] = self

    def features_request(self, event):
        msg = {
            'type': 'FEATURES_REPLY',
            'xid': event.xid,
            'flags': ['NO_ALERT'],
            'msg': {
                'datapath_id': self.datapath_id,
                'n_buffers': 0,
                'n_tables': 32,
                'capabilities': [],
                'ports': self._portdescs() if event.version < 4 else []
            }
        }
        ofp_compile(msg).send()

    def barrier_request(self, event):
        msg = {
            'type': 'BARRIER_REPLY',
            'xid': event.xid
        }
        ofp_compile(msg).send()

    def request_portdesc(self, event):
        msg = {
            'type': 'REPLY.PORT_DESC',
            'xid': event.xid,
            'msg': self._portdescs()
        }
        ofp_compile(msg).send()

    def request_desc(self, event):  # pylint: disable=no-self-use
        msg = {
            'type': 'REPLY.DESC',
            'xid': event.xid,
            'msg': {
                'hw_desc': 'hw_desc',
                'mfr_desc': 'mfr_desc',
                'sw_desc': 'sw_desc',
                'serial_num': '',
                'dp_desc': ''
            }
        }
        ofp_compile(msg).send()

    def _portdescs(self):
        return [self._portdesc(i) for i in range(1, 5)]

    def _portdesc(self, port_no):  # pylint: disable=no-self-use
        return {
            'port_no': port_no,
            'hw_addr': '00:00:00:00:00:FF',
            'name': 'port %d' % port_no,
            'config': [],
            'state': [],
            'ethernet': {
                'curr': [],
                'advertised': [],
                'supported': [],
                'peer': [],
                'curr_speed': 0,
                'max_speed': 0
            }
        }


app = ofp_app('simulator')
app.simulator_count = 100
app.exit_timeout = None
app.sims = []
app.conn_to_sim = {}


async def _exit_timeout(timeout):
    await asyncio.sleep(timeout)
    app.post_event('EXIT')


@app.event('start')
def start(_):
    if app.exit_timeout:
        app.ensure_future(_exit_timeout(app.exit_timeout))
    for i in range(app.simulator_count):
        sim = Simulator(hex(i + 1))  #'ff:ff:00:00:00:00:00:01')
        app.ensure_future(sim.start())


@app.message('features_request', datapath_id=None)
def features_request(event):
    app.conn_to_sim[event.conn_id].features_request(event)


@app.message('barrier_request', datapath_id=None)
def barrier_request(event):
    app.conn_to_sim[event.conn_id].barrier_request(event)


@app.message('request.port_desc', datapath_id=None)
def request_portdesc(event):
    app.conn_to_sim[event.conn_id].request_portdesc(event)


@app.message('request.desc', datapath_id=None)
def request_desc(event):
    app.conn_to_sim[event.conn_id].request_desc(event)


@app.message('channel_down', datapath_id=None)
def channel_down(event):
    sim = app.conn_to_sim.pop(event.conn_id, None)
    if sim:
        app.sims.remove(sim)


@app.message(any, datapath_id=None)
def other(event):
    app.logger.info('Unhandled message: %r' % event)


def main():
    args = parse_args()
    for module in args.modules:
        import_module(module)
    app.simulator_count = args.simulator_count
    app.exit_timeout = args.exit_timeout
    ofp_run(args=args, listen_endpoints=None)


def parse_args():
    parser = argparse.ArgumentParser(
        prog='simulator',
        description='Simulator Demo',
        parents=[ofp_default_args()])
    parser.add_argument(
        '--simulator-count', type=int, default=10, help='Number of datapaths to simulate')
    parser.add_argument(
        '--exit-timeout', type=float, default=0, help='Seconds to run simulation')
    parser.add_argument('modules', nargs='*', help='Modules to load')
    return parser.parse_args()


if __name__ == '__main__':
    main()
