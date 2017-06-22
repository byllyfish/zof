
def _convert_tp_dst(key, ofctl):
    return '%s_dst' % _ip_proto_name(ofctl)


def _convert_tp_src(key, ofctl):
    return '%s_src' % _ip_proto_name(ofctl)

_OFPVID_PRESENT = 0x1000

_IP_PROTO_NAME = { 6: 'tcp', 11: 'udp', 1: 'icmpv4', 58: 'icmpv6', 132: 'sctp'}

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
    result = {}
    for key, value in ofctl.items():
        key = convert_ofctl_field(key, ofctl)
        if key in result:
            raise ValueError('Duplicate ofctl field: %s' % key)
        result[key] = value
    vlan = result.get('vlan_vid')
    if vlan and isinstance(vlan, int):
        result['vlan_vid'] = vlan | _OFPVID_PRESENT
    return result


def convert_ofctl_field(key, ofctl):
    """Convert ofctl legacy field name."""
    conv = _LEGACY_FIELDS.get(key, key)
    return conv(key, ofctl) if callable(conv) else conv


def _ip_proto_name(ofctl):
    return _IP_PROTO_NAME[ofctl.get('ip_proto', None) or ofctl.get('nw_proto')]
