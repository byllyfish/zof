import zof
from ..http import HttpServer
from ..service.device import get_devices, get_device_port
from ..pktview import pktview_from_list

app = zof.Application('webserver')
app.http_endpoint = '127.0.0.1:8080'

web = HttpServer(logger=app.logger)
# web.define_var('dpid', _parse_dpid)


@app.event('start')
async def start(_):
    await web.start(app.http_endpoint)


@app.event('stop')
async def stop(_):
    await web.stop()


@web.get_json('/stats/switches')
def get_switches():
    return [d.datapath_id for d in get_devices()]


@web.get_json('/stats/flow/{dpid:[0-9A-F:]+}')
async def get_flows(dpid):
    result = await FLOW_REQ.request(datapath_id=_parse_dpid(dpid))
    _translate_flows(result.msg)
    return {dpid: result.msg}


@web.get_json('/stats/groupdesc/{dpid:[0-9A-F:]+}')
async def get_groupdesc(dpid):
    result = await GROUPDESC_REQ.request(datapath_id=_parse_dpid(dpid))
    _translate_groups(result.msg)
    return {dpid: result.msg}


@web.get_json('/stats/port/{dpid}/{port_no}')
async def get_portstats(dpid, port_no):
    result = await PORTSTATS_REQ.request(
        datapath_id=_parse_dpid(dpid), port_no=_parse_port(port_no))
    return {dpid: result.msg}


@web.post_json('/stats/portdesc/modify')
async def modify_portdesc(post_data):
    dpid = _parse_dpid(post_data.dpid)
    port_no = _parse_port(post_data.port_no)
    port = get_device_port(dpid, port_no)
    PORTMOD_REQ.send(
        datapath_id=dpid,
        port_no=port_no,
        hw_addr=port.hw_addr,
        config=post_data.config,
        mask=post_data.mask)
    # FIXME(bfish): This code does not handle OpenFlow errors elicited from the PortMod
    # message. Any errors returned will only show up in the log. The barrier here is
    # just a cheap trick to verify that the portmod *should* have been acted on.
    result = await BARRIER_REQ.request(datapath_id=dpid)
    return result.msg


FLOW_REQ = zof.compile('''
    type: REQUEST.FLOW
    msg:
        table_id: ALL
        out_port: ANY
        out_group: ANY
        cookie: 0
        cookie_mask: 0
        match: []
''')

GROUPDESC_REQ = zof.compile('''
    type: REQUEST.GROUP_DESC
''')

PORTSTATS_REQ = zof.compile('''
    type: REQUEST.PORT_STATS
    msg:
        port_no: $port_no
''')

PORTMOD_REQ = zof.compile('''
    type: PORT_MOD
    msg:
        port_no: $port_no
        hw_addr: $hw_addr
        config: [$config]
        mask: [$mask]
''')

BARRIER_REQ = zof.compile('''
    type: BARRIER_REQUEST
''')


def _parse_dpid(dpid):
    if isinstance(dpid, int):
        return _convert_dpid(dpid)
    if ':' in dpid:
        return dpid
    return _convert_dpid(int(dpid, 0))


def _convert_dpid(dpid):
    hexstr = '%16.16x' % dpid
    return ':'.join(hexstr[2 * i:2 * i + 2] for i in range(8))


def _parse_port(port_no):
    if isinstance(port_no, int):
        return port_no
    return int(port_no, 0)


def _translate_flows(msgs):
    for msg in msgs:
        if 'match' in msg:
            msg.match = pktview_from_list(msg.match, slash_notation=True)
        if 'instructions' in msg:
            msg.actions = _translate_instructions(msg.instructions)


def _translate_groups(msgs):
    for msg in msgs:
        for bkt in msg.buckets:
            if 'actions' in bkt:
                bkt.actions = _translate_actions(bkt.actions)


def _translate_instructions(instrs):
    result = []
    for instr in instrs:
        result += _translate_instruction(instr)
    return result


def _translate_instruction(instr):
    if instr.instruction == 'APPLY_ACTIONS':
        return _translate_actions(instr.actions)
    return [str(instr)]


def _translate_actions(actions):
    return [_translate_action(act) for act in actions]


def _translate_action(action):
    if action.action == 'OUTPUT':
        return 'OUTPUT:%s' % action.port_no
    if action.action == 'GROUP':
        return 'GROUP:%s' % action.group_id
    if action.action == 'SET_FIELD':
        return 'SET_FIELD: {%s:%s}' % (action.field.lower(), action.value)
    if len(action) == 1:
        return '%s' % action.action
    return str(action)


if __name__ == '__main__':
    zof.run()
