ofmsg = {
	'type': 'PACKET_OUT'
	'msg': {
	    'buffer_id': 'NO_BUFFER',
	    'in_port': 'CONTROLLER',
	    'actions': [ { 'action': 'OUTPUT', 'port_no': 1 }],
	    'data': '',
	    'pkt': {
	    	'eth_dst': '00:00:00:00:00:02',
	    	'eth_src': '00:00:00:00:00:01',
	    	'eth_type': 0x0800,
	    	'vlan_vid': 0x4196,
	    	'ipv4_src': '10.0.0.1',
	    	'ipv4_dst': '10.0.0.2',
	    	'nx_ip_ttl': 42,
	    	'icmpv4_type': 0,
	    	'icmpv4_code': 0,
	    	'payload': '0102030405060708'
	    }
	}
}
zof.compile(ofmsg).send(datapath_id=0x01)
