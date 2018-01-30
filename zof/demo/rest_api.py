import zof
from ..http import HttpServer
from ..pktview import pktview_from_list

APP = zof.Application('rest_api')
APP.http_endpoint = '127.0.0.1:8080'

WEB = HttpServer(logger=APP.logger)
# WEB.define_var('dpid', _parse_dpid)


@APP.event('start')
async def start(_):
    await WEB.start(APP.http_endpoint)


@APP.event('stop')
async def stop(_):
    await WEB.stop()


@WEB.get('/stats/switches', 'json')
def get_switches():
    return [d.datapath_id for d in zof.get_datapaths()]


@WEB.get('/stats/flow/{dpid}', 'json')
async def get_flows(dpid):
    result = []
    async for ofmsg in FLOW_REQ.request(datapath_id=_parse_dpid(dpid)):
        _translate_flows(ofmsg['msg'])
        result.extend(ofmsg['msg'])
    return {dpid: result}


@WEB.get('/stats/groupdesc/{dpid}', 'json')
async def get_groupdesc(dpid):
    result = await GROUPDESC_REQ.request(datapath_id=_parse_dpid(dpid))
    _translate_groups(result['msg'])
    return {dpid: result['msg']}


@WEB.get('/stats/port/{dpid}/{port_no}', 'json')
async def get_portstats_specific(dpid, port_no):
    result = await PORTSTATS_REQ.request(
        datapath_id=_parse_dpid(dpid), port_no=_parse_port(port_no))
    return {dpid: result['msg']}


@WEB.get('/stats/port/{dpid}', 'json')
async def get_portstats(dpid):
    result = await PORTSTATS_REQ.request(
        datapath_id=_parse_dpid(dpid), port_no='ANY')
    return {dpid: result['msg']}


@WEB.post('/stats/portdesc/modify', 'json')
async def modify_portdesc(post_data):
    dpid = _parse_dpid(post_data['dpid'])
    port_no = _parse_port(post_data['port_no'])
    port = zof.find_port(datapath_id=dpid, port_no=port_no)
    PORTMOD_REQ.send(
        datapath_id=dpid,
        port_no=port_no,
        hw_addr=port.hw_addr,
        config=post_data['config'],
        mask=post_data['mask'])
    # FIXME(bfish): This code does not handle OpenFlow errors elicited from the PortMod
    # message. Any errors returned will only show up in the log. The barrier here is
    # just a cheap trick to verify that the portmod *should* have been acted on.
    result = await BARRIER_REQ.request(datapath_id=dpid)
    return result['msg']


@WEB.get('/stats/portdesc/{dpid}', 'json')
async def get_portdesc(dpid):
    result = await PORTDESC_REQ.request(datapath_id=_parse_dpid(dpid))
    return {dpid: result['msg']}


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

PORTDESC_REQ = zof.compile('''
    type: REQUEST.PORT_DESC
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
            msg['match'] = pktview_from_list(msg['match'], slash_notation=True)
        if 'instructions' in msg:
            msg['actions'] = _translate_instructions(msg['instructions'])


def _translate_groups(msgs):
    for msg in msgs:
        for bkt in msg['buckets']:
            if 'actions' in bkt:
                bkt['actions'] = _translate_actions(bkt['actions'])


def _translate_instructions(instrs):
    result = []
    for instr in instrs:
        result += _translate_instruction(instr)
    return result


def _translate_instruction(instr):
    if instr['instruction'] == 'APPLY_ACTIONS':
        return _translate_actions(instr['actions'])
    return [str(instr)]


def _translate_actions(actions):
    return [_translate_action(act) for act in actions]


def _translate_action(action):
    action_type = action['action']
    if action_type == 'OUTPUT':
        return 'OUTPUT:%s' % action['port_no']
    if action_type == 'GROUP':
        return 'GROUP:%s' % action['group_id']
    if action_type == 'SET_FIELD':
        return 'SET_FIELD: {%s:%s}' % (action['field'].lower(),
                                       action['value'])
    if len(action) == 1:
        return '%s' % action_type
    return str(action)


if __name__ == '__main__':
    zof.run()
