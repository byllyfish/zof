"""Implements Rest API demo app."""

import zof
from zof.extra.http import HttpServer


class RestApi:
    """ZOF service implementing a REST API."""

    def __init__(self, endpoint):
        """Initialize RestAPI app."""
        self.web = HttpServer(endpoint)

        get_handlers = [
            ('/stats/switches', self.get_switches),
            ('/stats/flow/{dpid}', self.get_flows),
            ('/stats/groupdesc/{dpid}', self.get_groupdesc),
            ('/stats/port/{dpid}/{port_no}', self.get_portstats_specific),
            ('/stats/port/{dpid}', self.get_portstats),
            ('/stats/portdesc/{dpid}/{port_no}', self.get_portdesc_specific),
            ('/stats/portdesc/{dpid}', self.get_portdesc)
        ]

        post_handlers = [
            ('/stats/flow/{dpid}', self.post_flows),
            ('/stats/portdesc/modify', self.modify_portdesc)
        ]

        for route, func in get_handlers:
            self.web.get(route, 'json')(func)
        for route, func in post_handlers:
            self.web.post(route, 'json')(func)

    async def on_start(self):
        """Start service."""
        await self.web.start()

    async def on_stop(self):
        """Stop service."""
        await self.web.stop()

    async def _request(self, dpid, ofmsg):
        """Send OpenFlow request to a datapath."""
        dp = zof.find_datapath(dpid)
        if not dp:
            raise ValueError('Unknown dpid: %r' % dpid)
        return await dp.request(ofmsg)

    def _send(self, dpid, ofmsg):
        """Send OpenFlow message to a datapath."""
        dp = zof.find_datapath(dpid)
        if not dp:
            raise ValueError('Unknown dpid: %r' % dpid)
        dp.send(ofmsg)

    def get_switches(self):
        """Web handler for GET `/stats/switches`."""
        return [dp.id for dp in zof.get_datapaths()]

    async def get_flows(self, dpid):
        """Web handler for GET `/stats/flow/{dpid}`."""
        dpid = _parse_dpid(dpid)
        ofmsg = _flow_desc_request()
        result = await self._request(dpid, ofmsg)
        _translate_flows(result['msg'])
        return {dpid: result['msg']}

    async def post_flows(self, dpid, post_data):
        """Web handler for POST `/stats/flow/{dpid}`."""
        dpid = _parse_dpid(dpid)
        match = zof.Match(post_data.get('match', {})).to_list()
        ofmsg = _flow_desc_request(match=match, **post_data)
        result = await self._request(dpid, ofmsg)
        _translate_flows(result['msg'])
        return {dpid: result['msg']}

    async def get_groupdesc(self, dpid):
        """Web handler for GET `/stats/groupdesc/{dpid}`."""
        dpid = _parse_dpid(dpid)
        ofmsg = _group_desc_request()
        result = await self._request(dpid, ofmsg)
        _translate_groups(result['msg'])
        return {dpid: result['msg']}

    async def get_portstats_specific(self, dpid, port_no):
        """Web handler for GET `/stats/port/{dpid}/{port_no}`."""
        dpid = _parse_dpid(dpid)
        port_no = _parse_port(port_no)
        ofmsg = _port_stats_request(port_no)
        result = await self._request(dpid, ofmsg)
        return {dpid: result['msg']}

    async def get_portstats(self, dpid):
        """Web handler for GET `/stats/port/{dpid}`."""
        dpid = _parse_dpid(dpid)
        ofmsg = _port_stats_request()
        result = await self._request(dpid, ofmsg)
        return {dpid: result['msg']}

    async def modify_portdesc(self, post_data):
        """Web handler for POST `/stats/portdesc/modify`."""
        dpid = _parse_dpid(post_data['dpid'])
        port_no = _parse_port(post_data['port_no'])
        port = _find_port(dpid, port_no)
        ofmsg = _port_mod(
            port_no=port_no,
            hw_addr=port['hw_addr'],
            config=post_data['config'],
            mask=post_data['mask'])
        self._send(dpid, ofmsg)
        return {}

    async def get_portdesc_specific(self, dpid, port_no):
        """Web handler for GET `/stats/portdesc/{dpid}/{port_no}`."""
        dpid = _parse_dpid(dpid)
        port_no = _parse_port(port_no)
        ofmsg = _port_desc_request()
        result = await self._request(dpid, ofmsg)
        return {
            dpid:
            [desc for desc in result['msg'] if desc['port_no'] == port_no]
        }

    async def get_portdesc(self, dpid):
        """Web handler for GET `/stats/portdesc/{dpid}`."""
        dpid = _parse_dpid(dpid)
        ofmsg = _port_desc_request()
        result = await self._request(dpid, ofmsg)
        return {dpid: result['msg']}


def _parse_dpid(dpid):
    if isinstance(dpid, int):
        return dpid
    if ':' in dpid:
        return int(dpid.replace(':', ''), 16)
    return int(dpid, 0)


def _parse_port(port_no):
    if isinstance(port_no, int):
        return port_no
    try:
        return int(port_no, 0)
    except ValueError:
        return str(port_no).upper()


def _find_port(dpid, port_no):
    """Return specified datapath port."""
    dp = zof.find_datapath(dpid)
    if dp is None:
        raise ValueError('Unknown dpid: %r' % dpid)
    return dp.ports[port_no]


def _translate_flows(msgs):
    for msg in msgs:
        if 'match' in msg:
            msg['match'] = _translate_match(msg['match'])
        if 'instructions' in msg:
            msg['actions'] = _translate_instructions(msg['instructions'])
            del msg['instructions']


def _translate_groups(msgs):
    for msg in msgs:
        for bkt in msg['buckets']:
            if 'actions' in bkt:
                bkt['actions'] = _translate_actions(bkt['actions'])


def _translate_match(match):
    result = {}
    for item in match:
        field = item['field'].lower()
        value = item['value']
        mask = item.get('mask')
        if mask is not None:
            value = '%s/%s' % (value, mask)
        result[field] = value
    return result


def _translate_instructions(instrs):
    result = []
    for instr in instrs:
        result += _translate_instruction(instr)
    return result


def _translate_instruction(instr):
    if instr['instruction'] == 'APPLY_ACTIONS':
        return _translate_actions(instr['actions'])
    if instr['instruction'] == 'GOTO_TABLE':
        return ['GOTO_TABLE:%s' % instr['table_id']]
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
    if action_type == 'PUSH_VLAN':
        return 'PUSH_VLAN:%s' % action['ethertype']
    if len(action) == 1:
        return '%s' % action_type
    return str(action)


def _flow_desc_request(*, table_id='ALL',
                       out_port='ANY',
                       out_group='ANY',
                       cookie=0,
                       cookie_mask=0,
                       match=None):
    return {
        'type': 'FLOW_DESC_REQUEST',
        'msg': {
            'table_id': table_id,
            'out_port': out_port,
            'out_group': out_group,
            'cookie': cookie,
            'cookie_mask': cookie_mask,
            'match': match
        }
    }


def _group_desc_request():
    return {'type': 'GROUP_DESC_REQUEST'}


def _port_stats_request(port_no='ANY'):
    return {'type': 'PORT_STATS_REQUEST', 'msg': {'port_no': port_no}}


def _port_mod(*, port_no, hw_addr, config, mask):
    return {
        'type': 'PORT_MOD',
        'msg': {
            'port_no': port_no,
            'hw_addr': hw_addr,
            'config': [config],
            'mask': [mask],
            'advertise': []
        }
    }


def _port_desc_request():
    return {'type': 'PORT_DESC_REQUEST'}


if __name__ == '__main__':
    import asyncio
    app = RestApi(('127.0.0.1', 9000))
    asyncio.run(zof.run_controller(app))
