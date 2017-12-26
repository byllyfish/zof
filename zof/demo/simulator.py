import argparse
import asyncio
import zof
from zof.api_args import file_contents_type
import zof.exception as _exc


def _arg_parser():
    parser = argparse.ArgumentParser(
        prog='simulator', description='Simulator Demo', add_help=False)
    parser.add_argument(
        '--sim-endpoint',
        metavar='ENDPOINT',
        help='endpoint to connect to',
        default='127.0.0.1:6653')
    parser.add_argument(
        '--sim-count',
        type=int,
        default=10,
        help='Number of datapaths to simulate')
    parser.add_argument(
        '--sim-port-count',
        type=int,
        default=5,
        help='Number of ports per datapath')
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
    parser.add_argument(
        '--sim-reconnect',
        type=float,
        default=0,
        help='Reconnect retry interval (0=never)')
    return parser


APP = zof.Application(
    'simulator',
    exception_fatal=True,
    arg_parser=_arg_parser(),
    has_datapath_id=False)
APP.tls_id = 0
APP.conn_to_sim = {}
APP.connect_count = 0


async def _exit_timeout(timeout):
    await asyncio.sleep(timeout)
    zof.post_event({'event': 'SIM_TIMEOUT'})


@APP.event('sim_timeout')
def sim_timeout(_):
    exit_status = 20 if APP.connect_count < APP.args.sim_count else 0
    zof.post_event({'event': 'EXIT', 'exit_status': exit_status})


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
@APP.message('channel_alert')
@APP.message('flow_mod')
@APP.message('packet_out')
@APP.message('set_config')
@APP.message('set_async')
def ignore(event):
    APP.logger.warning('ignored %s msg', event['type'])


@APP.message('features_request')
def features_request(event):
    APP.connect_count += 1
    APP.conn_to_sim[event['conn_id']].features_request(event)


@APP.message('barrier_request')
def barrier_request(event):
    APP.conn_to_sim[event['conn_id']].barrier_request(event)


@APP.message('request.port_desc')
def request_portdesc(event):
    APP.conn_to_sim[event['conn_id']].request_portdesc(event)


@APP.message('request.desc')
def request_desc(event):
    APP.conn_to_sim[event['conn_id']].request_desc(event)


@APP.message('request.port_stats')
def request_portstats(event):
    APP.conn_to_sim[event['conn_id']].request_portstats(event)


@APP.message('request.table_features')
def request_tablefeatures(event):
    APP.conn_to_sim[event['conn_id']].request_tablefeatures(event)


@APP.message('channel_down')
def channel_down(event):
    APP.conn_to_sim[event['conn_id']].channel_down()


@APP.message('role_request')
def role_request(event):
    APP.conn_to_sim[event['conn_id']].role_request()


@APP.message(any)
def other(event):
    APP.logger.info('Unhandled message: %r', event)
    raise ValueError('Unexpected message: %r' % event)


class Simulator(object):
    # pylint: disable = no-self-use

    def __init__(self, datapath_id):
        self.datapath_id = datapath_id
        self.conn_id = None

    async def start(self):
        try:
            self.conn_id = await zof.connect(
                APP.args.sim_endpoint, versions=[4], tls_id=APP.tls_id)
            APP.conn_to_sim[self.conn_id] = self
        except _exc.RPCException:
            self.channel_down()

    def channel_down(self):
        APP.conn_to_sim.pop(self.conn_id, None)
        # If there's a reconnect interval, then schedule the restart.
        if APP.args.sim_reconnect:
            zof.ensure_future(self._restart(APP.args.sim_reconnect))

    def features_request(self, event):
        msg = {
            'type': 'FEATURES_REPLY',
            'xid': event['xid'],
            'flags': ['NO_ALERT'],
            'msg': {
                'datapath_id': self.datapath_id,
                'n_buffers': 0,
                'n_tables': 32,
                'capabilities': [],
                'ports': self._portdescs() if event['version'] < 4 else []
            }
        }
        zof.compile(msg).send()

    def barrier_request(self, event):
        msg = {'type': 'BARRIER_REPLY', 'xid': event['xid']}
        zof.compile(msg).send()

    def request_portdesc(self, event):
        msg = {
            'type': 'REPLY.PORT_DESC',
            'xid': event['xid'],
            'msg': self._portdescs()
        }
        zof.compile(msg).send()

    def request_desc(self, event):  # pylint: disable=no-self-use
        msg = {
            'type': 'REPLY.DESC',
            'xid': event['xid'],
            'msg': {
                'hw_desc': 'sim hw_desc',
                'mfr_desc': 'sim mfr_desc',
                'sw_desc': 'sim sw_desc',
                'serial_num': 'sim serial_num',
                'dp_desc': 'sim dp_desc'
            }
        }
        zof.compile(msg).send()

    def request_portstats(self, event):
        msg = {
            'type': 'REPLY.PORT_STATS',
            'xid': event['xid'],
            'msg': self._portstats()
        }
        zof.compile(msg).send()

    def request_tablefeatures(self, event):
        # This code currently ignores the contents of the TableFeatures request.
        msg = {
            'type': 'REPLY.TABLE_FEATURES',
            'xid': event['xid'],
            'msg': self._tablefeatures()
        }
        zof.compile(msg).send()

    def _portdescs(self):
        return [self._portdesc(i + 1) for i in range(APP.args.sim_port_count)]

    def _portdesc(self, port_no):  # pylint: disable=no-self-use
        macaddr = '%12.12x' % port_no
        return {
            'port_no': port_no,
            'hw_addr': macaddr,
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

    def _portstats(self):
        return [self._portstat(i + 1) for i in range(APP.args.sim_port_count)]

    def _portstat(self, port_no):
        return {
            'port_no': port_no,
            'duration': 0,
            'rx_packets': 0,
            'tx_packets': 0,
            'rx_bytes': 0,
            'tx_bytes': 0,
            'rx_dropped': 0,
            'tx_dropped': 0,
            'rx_errors': 0,
            'tx_errors': 0,
            'ethernet': {
                'rx_frame_err': 0,
                'rx_over_err': 0,
                'rx_crc_err': 0,
                'collisions': 0
            },
            'properties': []
        }

    def _tablefeatures(self):
        # FIXME(bfish): > 20, breaking into multipart request not working?
        return [self._tablefeature(i) for i in range(20)]

    def _tablefeature(self, table_id):
        actions = [hex(i) for i in range(100)]
        tables = list(range(table_id + 1, 254))
        return {
            'table_id': table_id,
            'name': 'Table %d' % table_id,
            'metadata_match': 0,
            'metadata_write': 0,
            'config': [0],
            'max_entries': 1024,
            'instructions': actions,
            'next_tables': tables,
            'write_actions': actions,
            'apply_actions': actions,
            'match': actions,
            'wildcards': actions,
            'write_set_field': actions,
            'apply_set_field': actions
        }

    async def _restart(self, interval):
        APP.logger.info('_restart in %d seconds', interval)
        await asyncio.sleep(interval)
        await self.start()


def main():
    args = zof.common_args(include_x_modules=True)
    args.set_defaults(listen_endpoints=None)
    zof.run(args=args.parse_args())


if __name__ == '__main__':
    main()
