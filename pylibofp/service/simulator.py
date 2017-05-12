from pylibofp import ofp_app, ofp_run, ofp_compile


class Simulator(object):

    def __init__(self, datapath_id):
        self.datapath_id = datapath_id
        app.sims.append(self)

    async def start(self, event):
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

    def request_portdesc(self, event):
        msg = {
            'type': 'REPLY.PORT_DESC',
            'xid': event.xid,
            'msg': self._portdescs()
        }
        ofp_compile(msg).send()

    def request_desc(self, event):
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


app = ofp_app('simulator')
app.sims = []
app.conn_to_sim = {}


@app.event('start')
def start(event):
    for i in range(500):
        sim = Simulator(hex(i+1))  #'ff:ff:00:00:00:00:00:01')
        app.ensure_future(sim.start(event))


@app.message('features_request', datapath_id=None)
def features_request(event):
    app.conn_to_sim[event.conn_id].features_request(event)


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


if __name__ == '__main__':
    import pylibofp.service.device
    ofp_run(
        oftr_args=['--loglevel=info', '--logfile=oftr.log']
    )
