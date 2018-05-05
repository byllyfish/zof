
"""
ZOF represents OpenFlow messages as Python dictionaries based on a JSON DSL.

This module provides utility functions for constructing the most common OpenFlow
messages used by OpenFlow controllers.

	flow_mod
		flow_add
		flow_delete
		flow_modify
	group_mod
	packet_out
	set_config

"""


def gen_msg(type_, xid=None, **kwds):
	"""Generate an OpenFlow message.

	Example:

		ofmsg = gen_msg('SET_CONFIG', 
					flags=['FRAG_NORMAL'], 
					miss_send_len='NO_BUFFER')
	"""
	result = { 'type': type_, 'msg': kwds }
	if xid is not None:
		result['xid'] = xid
	return result


def set_config(flags=None, miss_send_len=0):
	return gen_msg('SET_CONFIG', flags=flags, miss_send_len=miss_send_len)



def gen_action(action, **kwds):
	result = { 'action': action }
	result.update(kwds)
	return result


def gen_instr(instruction, **kwds):
	result = { 'instruction': instruction }
	result.update(kwds)
	return result


def gen_field(key, value):
	if '/' in value:
		value, mask = value.split('/', 1)
		return { 'field': key, 'value': value, 'mask': mask }
	return { 'field': key, 'value': value }


def match(**kwds):
	return [gen_field(key, value) for key, value in kwds.items()]


def _output(*, port_no, max_len=0):
	return gen_action('OUTPUT', port_no=port_no, max_len=max_len)


def _apply_actions(actions):
	return gen_instr('APPLY_ACTIONS', actions=actions)


def _goto_table(table_id):
	return gen_instr('GOTO_TABLE', table_id=table_id)


msg.set_config = _set_config
action.output = _output
instr.apply_actions = _apply_actions
instr.goto_table = _goto_table
action.goto_table = _goto_table


def flowmod(*, table_id, command='ADD', match=None, actions=None):
	"""Construct a FlowMod message.

	Example:

		ofmsg = ofp.flowmod(table_id=0, command='ADD', match=ofp.match(eth_type=0x0800), 
								actions=[ofp.output(1), ofp.goto_table(1)]
	"""
	return msg('FLOW_MOD', 
				table_id=table_id, 
				command=command, 
				match=match, 
				instructions=_instr_convert(actions))
