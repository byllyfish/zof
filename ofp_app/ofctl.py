try:
    # For Python 2.x compatibility.
    _BASESTRING = basestring
except NameError:
    _BASESTRING = str


def _convert_tp_dst(_key, ofctl):
    return '%s_dst' % _ip_proto_name(ofctl)


def _convert_tp_src(_key, ofctl):
    return '%s_src' % _ip_proto_name(ofctl)


def _convert_vlan(vlan):
    if isinstance(vlan, _BASESTRING):
        vlan = int(vlan, 0)
    if vlan > 0:
        vlan |= _OFPVID_PRESENT
    return vlan


_OFPVID_PRESENT = 0x1000

_IP_PROTO_NAME = {6: 'tcp', 11: 'udp', 1: 'icmpv4', 58: 'icmpv6', 132: 'sctp'}

_LEGACY_FIELDS = dict(
    dl_type='eth_type',
    dl_src='eth_src',
    dl_dst='eth_dst',
    dl_vlan='vlan_vid',
    nw_src='ipv4_src',
    nw_dst='ipv4_dst',
    nw_proto='ip_proto',
    tp_dst=_convert_tp_dst,
    tp_src=_convert_tp_src)


def convert_from_ofctl(ofctl):
    """Convert ofctl legacy field names."""
    if ofctl is None:
        return None
    result = {}
    for key, value in ofctl.items():
        key = convert_ofctl_field(key, ofctl)
        if key in result:
            raise ValueError('Duplicate ofctl field: %s' % key)
        result[key] = value
    if 'vlan_vid' in result:
        result['vlan_vid'] = _convert_vlan(result['vlan_vid'])
    return result


def convert_ofctl_field(key, ofctl):
    """Convert ofctl legacy field name."""
    conv = _LEGACY_FIELDS.get(key, key)
    return conv(key, ofctl) if callable(conv) else conv


def _ip_proto_name(ofctl):
    proto = ofctl.get('ip_proto') or ofctl.get('nw_proto')
    if proto is None:
        return 'tcp'
    try:
        return _IP_PROTO_NAME[proto]
    except KeyError:
        raise ValueError('Unknown ip_proto %s' % proto)
