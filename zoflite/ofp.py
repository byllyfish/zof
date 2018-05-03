


def msg(type_, xid=None, **kwds):
	"""Generate an OpenFlow message.

	Example:

		ofmsg = msg('SET_CONFIG', 
					flags=['FRAG_NORMAL'], 
					miss_send_len='NO_BUFFER')
	"""
	result = { 'type': type_, 'msg': kwds }
	if xid is not None:
		result['xid'] = xid
	return result


def _set_config(flags=(), miss_send_len='MAX'):
	return msg('SET_CONFIG', flags=flags, miss_send_len=miss_send_len)



def action(action, **kwds):
	result = { 'action': action }
	result.update(kwds)
	return result


def instr(instruction, **kwds):
	result = { 'instruction': instruction }
	result.update(kwds)
	return result


def field(key, value):
	if '/' in value:
		value, mask = value.split('/', 1)
		return { 'field': key, 'value': value, 'mask': mask }
	return { 'field': key, 'value': value }

def match(**kwds):
	return [field(key, value) for key, value in kwds.items()]


def _output(*, port_no, max_len=0):
	return action('OUTPUT', port_no=port_no, max_len=max_len)


def _apply_actions(actions):
	return instr('APPLY_ACTIONS', actions=actions)


msg.set_config = _set_config
action.output = _output
instr.apply_actions = _apply_actions

