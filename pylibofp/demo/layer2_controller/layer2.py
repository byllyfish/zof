"""Layer2 Demo App

- Implements forwarding for a vlan-aware layer 2 switch.
- Ignores LLDP packets.
"""

from pylibofp import ofp_app
from pylibofp.pktview import pktview_from_list
from . import ofmsg

COOKIE = 0x1BF0C0031E

app = ofp_app('layer2')

# The forwarding table is a dictionary that maps:
#   (eth_dst, vlan_vid) -> (out_port, time)
forwarding_table = {}


def _is_lldp(eth_type):
    return eth_type == 0x88cc


def _is_unicast(eth_src):
    return eth_src[1] in '02468ace'


@app.message('channel_up')
def channel_up(event):
    """Set up datapath when switch connects."""
    app.logger.debug('channel up %r', event)

    ofmsg.delete_flows.send(cookie=COOKIE)
    ofmsg.barrier.send()
    ofmsg.table_miss_flow.send(cookie=COOKIE)


@app.message('channel_down')
def channel_down(event):
    """Clean up when switch disconnects."""
    forwarding_table.pop(event.datapath_id, None)


@app.message('packet_in', eth_type=_is_lldp)
def lldp_packet_in(_event):
    """Ignore lldp packets."""
    app.logger.debug('lldp packet ignored')


@app.message('packet_in')
def packet_in(event):
    """Handle incoming packets."""
    app.logger.debug('packet in %r', event)
    msg = event.msg

    # Check for incomplete packet data.
    if len(msg.data) < msg.total_len:
        app.logger.warning('Incomplete packet data: %r', event)
        return

    in_port = msg.in_port
    eth_src = msg.pkt.eth_src
    eth_dst = msg.pkt.eth_dst
    vlan_vid = msg.pkt('vlan_vid', default=0)

    if not _is_unicast(eth_src):
        out_port = 'ALL'
    else:
        # Retrieve fwd_table for this datapath. Update fwd_table with 
        # ethernet source address. Lookup output port for destination address.
        # If not found, set output port to 'ALL'.
        fwd_table = forwarding_table.setdefault(event.datapath_id, {})
        if (eth_src, vlan_vid) not in fwd_table:
            app.logger.info('Learn %s vlan %s on port %s', eth_src, vlan_vid, in_port)
            fwd_table[(eth_src, vlan_vid)] = (in_port, event.time)
        out_port, _ = fwd_table.get((eth_dst, vlan_vid), ('ALL', None))

    if out_port != 'ALL':
        app.logger.info('Forward %s vlan %s to port %s', eth_dst, vlan_vid, out_port)
        ofmsg.learn_mac_flow.send(
            in_port=in_port,
            vlan_vid=vlan_vid,
            eth_dst=eth_dst,
            out_port=out_port,
            cookie=COOKIE)

    # Send packet back out the correct port.
    ofmsg.packet_out.send(in_port=in_port, out_port=out_port, data=msg.data)


@app.message('flow_removed', cookie=COOKIE)
def flow_removed(event):
    """Handle flow removed message."""
    match = pktview_from_list(event.msg.match)
    eth_dst = match.eth_dst
    vlan_vid = match.vlan_vid
    reason = event.msg.reason

    app.logger.info('Remove %s vlan %s (%s)', eth_dst, vlan_vid, reason)

    fwd_table = forwarding_table.get(event.datapath_id)
    if fwd_table:
        fwd_table.pop((eth_dst, vlan_vid), None)


#@app.message('port_status')
#def port_status(event):
#    pass


@app.message('all')
def other_message(event):
    """Log unhandled messages."""
    app.logger.warning('Unhandled message: %r', event)
