# demo
import ofp


class L2Switch:
	L2_TIMEOUT = 300

	def start(self):
		pass

	def stop(self):
		pass

	def channel_up(self, dp, event):
		for ofmsg in INIT_TABLES:
			dp.send(ofmsg)

	def packet_in(self, dp, event):
		msg = event['msg']
		pkt = msg['pkt']
		for ofmsg in l2_learn(pkt['eth_src'], msg['in_port'], self.L2_TIMEOUT):
			dp.send(ofmsg)


INIT_TABLES = [
	ofp.flow_mod(command='DELETE', table_id=0),
	ofp.flow_mod(command='DELETE', table_id=1),
	ofp.barrier(),
	ofp.flow_mod(command='ADD', table_id=0, apply_actions=[ofp.output_port('CONTROLLER', maxlen=128)], goto_table=1)
	ofp.flow_mod(command='ADD', table_id=1, apply_actions=[ofp.output_port('ALL')])
]

def l2_learn(eth_src, in_port, timeout)
	src_match = ofp.match(eth_src=eth_src)
	dst_match = ofp.match(eth_dst=eth_src)
	src_port_match = ofp.match(eth_src=eth_src, in_port=in_port)
	return [
		ofp.flow_mod(command='DELETE', table_id=0, match=src_match),
		ofp.flow_mod(command='DELETE', table_id=1, match=dst_match),
		ofp.barrier(),
		ofp.flow_mod(command='ADD', table_id=0, priority=100, hard_timeout=timeout, match=src_port_match, goto_table=1),
		ofp.flow_mod(command='ADD', table_id=1, priority=100, hard_timeout=timeout+2, match=dst_match, apply_actions=[ofp.output_port(in_port)])
	]

if __name__ == '__main__':
	coro = zof.run(L2Switch())
	asyncio.run_until_complete(coro)


