"""Layer 2 demo."""

import asyncio
import logging
import zof


class Layer2(zof.Controller):
    """Demo layer2 OpenFlow app."""

    def __init__(self, config=None):
        super().__init__(config)
        self.forwarding_table = {}
        self.logger = logging.getLogger('layer2')
        self.logger.setLevel(logging.INFO)

    def on_start(self):
        """Handle start event."""
        self.logger.info('Listening on %s', self.zof_config.listen_endpoints)

    def on_channel_up(self, dp, event):
        """Handle CHANNEL_UP event."""
        msg = event['msg']
        self.logger.info('%s Connected from %s (%d ports, version %d)', dp.id,
                         msg['endpoint'], len(msg['features']['ports']),
                         event['version'])
        self.logger.info('%s Remove all flows', dp.id)

        ofmsgs = [_delete_flows(), _barrier(), _table_miss()]
        for ofmsg in ofmsgs:
            dp.send(ofmsg)

    def on_channel_down(self, dp, _event):
        """Handle CHANNEL_DOWN event."""
        self.logger.info('%s Disconnected', dp.id)
        self.forwarding_table.pop(dp.id, None)

    def on_packet_in(self, dp, event):
        """Handle PACKET_IN event."""
        self.logger.debug('PACKET_IN %r', event)

        msg = event['msg']
        in_port = msg['in_port']
        data = msg['data']
        pkt = msg['pkt']

        # Drop LLDP.
        if pkt.eth_type == 0x88cc:
            self.logger.warning('Ignore LLDP')
            return

        # Check for incomplete packet data.
        if len(data) < msg['total_len']:
            self.logger.warning('Incomplete packet data: %r', event)
            return

        # Retrieve fwd_table for this datapath.
        fwd_table = self.forwarding_table.setdefault(dp.id, {})

        # Update fwd_table based on eth_src and in_port.
        if pkt.eth_src not in fwd_table:
            self.logger.info('%s Learn %s on port %s', dp.id, pkt.eth_src,
                             in_port)
            fwd_table[pkt.eth_src] = in_port

        # Lookup output port for eth_dst. If not found, use 'ALL'.
        out_port = fwd_table.get(pkt.eth_dst, 'ALL')

        ofmsgs = []
        if out_port != 'ALL':
            self.logger.info('%s Forward %s to port %s', dp.id, pkt.eth_dst,
                             out_port)
            ofmsgs.append(_table_learn(pkt.eth_dst, out_port))

        ofmsgs.append(_packet_out(out_port, data))

        for ofmsg in ofmsgs:
            dp.send(ofmsg)

    def on_flow_removed(self, dp, event):
        """Handle FLOW_REMOVED event."""
        msg = event['msg']
        match = {
            field['field'].lower(): field['value']
            for field in msg['match']
        }
        eth_dst = match['eth_dst']
        self.logger.info('%s Remove %s (%s)', dp.id, eth_dst, msg['reason'])


def _delete_flows():
    """Delete all flows in table 0."""
    return {'type': 'FLOW_MOD', 'msg': {'command': 'DELETE', 'table_id': 0}}


def _barrier():
    """Barrier request."""
    return {'type': 'BARRIER_REQUEST'}


def _table_miss():
    """Add default flow to table 0 that sends packets to controller."""
    return {
        'type': 'FLOW_MOD',
        'msg': {
            'command': 'ADD',
            'table_id': 0,
            'priority': 0,
            'instructions': [_apply_actions([_output('CONTROLLER')])]
        }
    }


def _table_learn(eth_dst, out_port):
    """Add flow to table 0 to forward layer2 packets."""
    return {
        'type': 'FLOW_MOD',
        'msg': {
            'command': 'ADD',
            'table_id': 0,
            'hard_timeout': 60,
            'priority': 10,
            'flags': ['SEND_FLOW_REM'],
            'match': _match(eth_dst=eth_dst),
            'instructions': [_apply_actions([_output(out_port)])]
        }
    }


def _packet_out(out_port, data):
    return {
        'type': 'PACKET_OUT',
        'msg': {
            'actions': [_output(out_port)],
            'data': data
        }
    }


def _apply_actions(actions):
    return {'instruction': 'APPLY_ACTIONS', 'actions': actions}


def _output(port):
    return {'action': 'OUTPUT', 'port_no': port}


def _match(**kwds):
    return [{
        'field': key.upper(),
        'value': value
    } for key, value in kwds.items()]


if __name__ == '__main__':
    logging.basicConfig()
    asyncio.run(Layer2().run())  # type: ignore
