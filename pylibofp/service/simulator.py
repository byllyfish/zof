from pylibofp import ofp_app, ofp_run, ofp_compile


class Simulator(object):
    simcount = 0

    def __init__(self, datapath_id):
        self.datapath_id = datapath_id
        self.conn_id = None
        Simulator.simcount += 1
        self.app = ofp_app('simulator_%d' % Simulator.simcount)
        self.app.subscribe(self.start, 'event', 'start', {})

    async def start(self, event):
        self.conn_id = await self.app.connect('127.0.0.1:6653', versions=[1])
        self.app.logger.debug('start %d', self.conn_id)
        self.app.set_filter('message', lambda evt: evt.conn_id == self.conn_id)
        self.app.subscribe(self.features_request, 'message',
                           'FEATURES_REQUEST', {'datapath_id': None})
        self.app.subscribe(self.request_desc, 'message', 'REQUEST.DESC',
                           {'datapath_id': None})
        self.app.subscribe(self.request_portdesc, 'message',
                           'REQUEST.PORT_DESC', {'datapath_id': None})

    def features_request(self, event):
        self.app.logger.debug('features_request entered %r', event)
        msg = {
            'type': 'FEATURES_REPLY',
            'xid': event.xid,
            'msg': {
                'datapath_id': self.datapath_id,
                'n_buffers': 0,
                'n_tables': 32,
                'capabilities': [],
                'ports': []
            }
        }
        ofp_compile(msg).send()

    def request_portdesc(self, event):
        msg = {
            'type': 'REPLY.PORT_DESC',
            'xid': event.xid,
            'msg': [self._portdesc(i) for i in range(1, 5)]
        }
        ofp_compile(msg).send()

    def request_desc(self, event):
        self.app.logger.debug('desc_request entered')
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

    def _portdesc(self, port_no):
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


if __name__ == '__main__':
    import pylibofp.service.device
    for i in range(1000):
        sim = Simulator('ff:ff:00:00:00:00:00:01')
    ofp_run(
        command_prompt=None
        #oftr_args=['--trace=rpc', '--loglevel=debug', '--logfile=oftr.log']
    )
