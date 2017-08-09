import argparse
import asyncio
import zof
from zof.api_args import file_contents_type


def _arg_parser():
    parser = argparse.ArgumentParser(
        prog='simulator', description='Simulator Demo', add_help=False)
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
        '--sim-cert', type=file_contents_type(), help='Simulator certificate')
    parser.add_argument(
        '--sim-privkey',
        type=file_contents_type(),
        help='Simulator private key')
    parser.add_argument(
        '--sim-cacert',
        type=file_contents_type(),
        help='Simulator CA certificate')
    return parser


APP = zof.Application(
    'simulator',
    exception_fatal=True,
    arg_parser=_arg_parser(),
    has_datapath_id=False)
APP.tls_id = 0
APP.sims = []
APP.conn_to_sim = {}
APP.connect_count = 0


async def _exit_timeout(timeout):
    await asyncio.sleep(timeout)
    zof.post_event('SIM_TIMEOUT')


@APP.event('sim_timeout')
def sim_timeout(_):
    exit_status = 20 if APP.connect_count < APP.args.sim_count else 0
    zof.post_event('EXIT', exit_status=exit_status)


@APP.event('prestart')
async def prestart(_):
    if APP.args.sim_cert:
        APP.tls_id = await zof.add_identity(
            cert=APP.args.sim_cert,
            cacert=APP.args.sim_cacert,
            privkey=APP.args.sim_privkey)


@APP.event('start')
def start(_):
    if APP.args.sim_timeout:
        zof.ensure_future(_exit_timeout(APP.args.sim_timeout))
    for i in range(APP.args.sim_count):
        sim = Simulator(hex(i + 1))  # 'ff:ff:00:00:00:00:00:01')
        zof.ensure_future(sim.start())


@APP.message('channel_up')
@APP.message('flow_mod')
def ignore(_):
    return


@APP.message('features_request')
def features_request(event):
    APP.connect_count += 1
    APP.conn_to_sim[event.conn_id].features_request(event)


@APP.message('barrier_request')
def barrier_request(event):
    APP.conn_to_sim[event.conn_id].barrier_request(event)


@APP.message('request.port_desc')
def request_portdesc(event):
    APP.conn_to_sim[event.conn_id].request_portdesc(event)


@APP.message('request.desc')
def request_desc(event):
    APP.conn_to_sim[event.conn_id].request_desc(event)


@APP.message('channel_down')
def channel_down(event):
    sim = APP.conn_to_sim.pop(event.conn_id, None)
    if sim:
        APP.sims.remove(sim)


@APP.message(any)
def other(event):
    APP.logger.info('Unhandled message: %r', event)
    raise ValueError('Unexpected message: %r' % event)


class Simulator(object):
    # pylint: disable = no-self-use

    def __init__(self, datapath_id):
        self.datapath_id = datapath_id
        APP.sims.append(self)

    async def start(self):
        conn_id = await zof.connect(
            '127.0.0.1:6653', versions=[4], tls_id=APP.tls_id)
        APP.conn_to_sim[conn_id] = self

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
        zof.compile(msg).send()

    def barrier_request(self, event):
        msg = {'type': 'BARRIER_REPLY', 'xid': event.xid}
        zof.compile(msg).send()

    def request_portdesc(self, event):
        msg = {
            'type': 'REPLY.PORT_DESC',
            'xid': event.xid,
            'msg': self._portdescs()
        }
        zof.compile(msg).send()

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
        zof.compile(msg).send()

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
    args = zof.common_args(include_x_modules=True)
    args.set_defaults(listen_endpoints=None)
    zof.run(args=args.parse_args())


if __name__ == '__main__':
    main()
