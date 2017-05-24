from pylibofp import ofp_app, ofp_run, ofp_compile
from pylibofp.http import HttpServer
from pylibofp.service.device import get_devices


app = ofp_app('webserver')
web = HttpServer('8080', logger=app.logger)

@app.event('start')
async def start(_):
    await web.start()

@app.event('stop')
async def stop(_):
    await web.stop()


@web.route(r'/stats/switches')
def get_switches():
    return [d.datapath_id for d in get_devices()]


@web.route(r'/stats/flow/{dpid:[0-9A-F:]+}')
async def get_flows(dpid):
    result = await FLOW_REQ.request(datapath_id=_parse_dpid(dpid))
    return result.msg


@web.route(r'/stats/groupdesc/{dpid:[0-9A-F:]+}')
async def get_groupdesc(dpid):
    result = await GROUPDESC_REQ.request(datapath_id=_parse_dpid(dpid))
    return result.msg


@web.route(r'/stats/port/{dpid}/{port_no}')
async def get_portstats(dpid, port_no):
    result = await PORTSTATS_REQ.request(datapath_id=_parse_dpid(dpid), port_no=_parse_port(port_no))
    return result.msg


FLOW_REQ = ofp_compile('''
    type: REQUEST.FLOW
    msg:
        table_id: ALL
        out_port: ANY
        out_group: ANY
        cookie: 0
        cookie_mask: 0
        match: []
''')

GROUPDESC_REQ = ofp_compile('''
    type: REQUEST.GROUP_DESC
''')


PORTSTATS_REQ = ofp_compile('''
    type: REQUEST.PORT_STATS
    msg:
        port_no: $port_no
''')


def _parse_dpid(dpid):
    if ':' in dpid:
        return dpid
    return hex(int(dpid, 0))


def _parse_port(port_no):
    return int(port_no, 0)


if __name__ == '__main__':
    ofp_run()
