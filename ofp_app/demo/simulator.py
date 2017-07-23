import argparse
import asyncio
import ofp_app
from ofp_app.api_args import file_content


def arg_parser():
    parser = argparse.ArgumentParser(
        prog='simulator',
        description='Simulator Demo')
    parser.add_argument(
        '--sim-count',
        type=int,
        default=10,
        help='Number of datapaths to simulate')
    parser.add_argument(
        '--sim-timeout',
        type=float,
        default=0,
        help='Seconds to run simulation')
    parser.add_argument(
        '--sim-cert', type=file_content, help='Simulator certificate')
    parser.add_argument(
        '--sim-privkey', type=file_content, help='Simulator private key')
    parser.add_argument(
        '--sim-cacert', type=file_content, help='Simulator CA certificate')
    return parser


app = ofp_app.Application('simulator', exception_fatal=True, arg_parser=arg_parser())
app.tls_id = 0
app.sims = []
app.conn_to_sim = {}
app.connect_count = 0


async def _exit_timeout(timeout):
    await asyncio.sleep(timeout)
    app.post_event('SIM_TIMEOUT')


@app.event('sim_timeout')
def sim_timeout(_):
    exit_status = 20 if app.connect_count < app.args.sim_count else 0
    app.post_event('EXIT', exit_status=exit_status)


@app.event('prestart')
async def prestart(_):
    if app.args.sim_cert:
        result = await app.rpc_call(
            'OFP.ADD_IDENTITY',
            cert=app.args.sim_cert,
            cacert=app.args.sim_cacert,
            privkey=app.args.sim_privkey)
        app.tls_id = result.tls_id


@app.event('start')
def start(_):
    if app.args.sim_timeout:
        app.ensure_future(_exit_timeout(app.args.sim_timeout))
    for i in range(app.args.sim_count):
        sim = Simulator(hex(i + 1))  #'ff:ff:00:00:00:00:00:01')
        app.ensure_future(sim.start())


@app.message('channel_up', datapath_id=None)
@app.message('flow_mod', datapath_id=None)
def ignore(_):
    return


@app.message('features_request', datapath_id=None)
def features_request(event):
    app.connect_count += 1
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
    app.logger.info('Unhandled message: %r', event)
    raise ValueError('Unexpected message: %r' % event)


class Simulator(object):
    # pylint: disable = no-self-use

    def __init__(self, datapath_id):
        self.datapath_id = datapath_id
        app.sims.append(self)

    async def start(self):
        conn_id = await app.connect(
            '127.0.0.1:6653', versions=[4], tls_id=app.tls_id)
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
        ofp_app.compile(msg).send()

    def barrier_request(self, event):
        msg = {'type': 'BARRIER_REPLY', 'xid': event.xid}
        ofp_app.compile(msg).send()

    def request_portdesc(self, event):
        msg = {
            'type': 'REPLY.PORT_DESC',
            'xid': event.xid,
            'msg': self._portdescs()
        }
        ofp_app.compile(msg).send()

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
        ofp_app.compile(msg).send()

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


def main():
    args = ofp_app.common_args()
    args.set_defaults(listen_endpoints=None)
    ofp_app.run(args=args.parse_args())

if __name__ == '__main__':
    main()
