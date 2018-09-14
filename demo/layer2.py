"""Layer 2 demo."""

import asyncio
from collections import defaultdict
import zof

FLOOD = 'ALL'


class Layer2(zof.Controller):
    def __init__(self, config=None):
        super().__init__(config)
        self.mac_to_port = defaultdict(dict)

    def on_channel_up(self, dp, _event):
        actions = [output('CONTROLLER', 'NO_BUFFER')]
        ofmsg = flowmod(priority=0, actions=actions)
        dp.send(ofmsg)

    def on_packet_in(self, dp, event):
        msg = event['msg']
        pkt = msg['pkt']

        in_port = msg['in_port']
        self.mac_to_port[dp.id][pkt.eth_src] = in_port
        out_port = self.mac_to_port[dp.id].get(pkt.eth_dst, FLOOD)

        actions = [output(out_port)]

        if out_port != FLOOD:
            match = flowmatch(
                in_port=in_port, eth_dst=pkt.eth_dst, eth_src=pkt.eth_src)
            ofmsg = flowmod(
                priority=1,
                match=match,
                actions=actions,
                buffer_id=msg['buffer_id'])
            dp.send(ofmsg)

            if msg['buffer_id'] != 'NO_BUFFER':
                return

        data = msg['data'] if msg['buffer_id'] == 'NO_BUFFER' else b''
        ofmsg = packet_out(
            buffer_id=msg['buffer_id'],
            in_port=in_port,
            actions=actions,
            data=data)
        dp.send(ofmsg)


def flowmod(table_id=0,
            priority=0,
            match=None,
            actions=None,
            buffer_id='NO_BUFFER'):
    instructions = [apply_actions(actions)] if actions else None
    return {
        'type': 'FLOW_MOD',
        'msg': {
            'table_id': table_id,
            'command': 'ADD',
            'buffer_id': buffer_id,
            'priority': priority,
            'match': match,
            'instructions': instructions
        }
    }


def apply_actions(actions):
    return {'instruction': 'APPLY_ACTIONS', 'actions': actions}


def output(port, maxlen=0):
    return {'action': 'OUTPUT', 'port_no': port, 'max_len': maxlen}


def packet_out(buffer_id='NO_BUFFER', in_port=0, actions=None, data=b''):
    return {
        'type': 'PACKET_OUT',
        'msg': {
            'buffer_id': buffer_id,
            'in_port': in_port,
            'actions': actions,
            'data': data
        }
    }


def flowmatch(**kwds):
    return [{'field': key.upper(), 'value': value} for key, value in kwds.items()]


if __name__ == '__main__':
    asyncio.run(Layer2().run())  # type: ignore
