"""Layer2 Demo App

- Implements reactive forwarding for a vlan-aware layer 2 switch.
- Ignores LLDP packets.
- Does not support loops.

"""

from pylibofp import ofp_app
from pylibofp.pktview import pktview_from_list
from . import ofmsg


app = ofp_app('layer2')

# The forwarding table is a dictionary that maps:
#   datapath_id -> { (eth_dst, vlan_vid) -> (out_port, time) }

app.forwarding_table = {}


@app.message('channel_up')
def channel_up(event):
    """Set up datapath when switch connects."""
    app.logger.info('%s Connected', event.datapath_id)
    app.logger.info('%s Remove all flows', event.datapath_id)

    ofmsg.delete_flows.send()
    ofmsg.barrier.send()
    ofmsg.table_miss_flow.send()


@app.message('channel_down')
def channel_down(event):
    """Clean up when switch disconnects."""
    app.logger.info('%s Disconnected', event.datapath_id)
    app.forwarding_table.pop(event.datapath_id, None)


@app.message('packet_in', eth_type=0x88cc)
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
    pkt = msg.pkt
    vlan_vid = pkt('vlan_vid', default=0)

    # Retrieve fwd_table for this datapath. 
    fwd_table = app.forwarding_table.setdefault(event.datapath_id, {})

    # Update fwd_table based on eth_src and in_port.
    if (pkt.eth_src, vlan_vid) not in fwd_table:
        app.logger.info('%s Learn %s vlan %s on port %s', event.datapath_id, pkt.eth_src, vlan_vid, in_port)
        fwd_table[(pkt.eth_src, vlan_vid)] = (in_port, event.time)

    # Lookup output port for eth_dst. If not found, set output port to 'ALL'.
    out_port, _ = fwd_table.get((pkt.eth_dst, vlan_vid), ('ALL', None))

    if out_port != 'ALL':
        app.logger.info('%s Forward %s vlan %s to port %s', event.datapath_id, pkt.eth_dst, vlan_vid, out_port)
        ofmsg.learn_mac_flow.send(
            vlan_vid=vlan_vid,
            eth_dst=pkt.eth_dst,
            out_port=out_port)
        ofmsg.packet_out.send(out_port=out_port, data=msg.data)

    else:
        # Send packet back out all ports (except the one it came in).
        app.logger.info('%s Flood %s packet to %s vlan %s', event.datapath_id, pkt.pkt_type, pkt.eth_dst, vlan_vid)
        ofmsg.packet_flood.send(in_port=in_port, data=msg.data)


@app.message('flow_removed')
def flow_removed(event):
    """Handle flow removed message."""
    match = pktview_from_list(event.msg.match)
    eth_dst = match.eth_dst
    vlan_vid = match.vlan_vid
    reason = event.msg.reason

    app.logger.info('%s Remove %s vlan %s (%s)', event.datapath_id, eth_dst, vlan_vid, reason)

    fwd_table = app.forwarding_table.get(event.datapath_id)
    if fwd_table:
        fwd_table.pop((eth_dst, vlan_vid), None)


@app.message(any)
def other_message(event):
    """Log ignored messages."""
    app.logger.debug('Ignored message: %r', event)
