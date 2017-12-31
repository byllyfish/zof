# N.B. This module must remain compatibile with Python 2.7.

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
_ETHTYPE_ARP = 0x0806

_IP_PROTO_NAME = {6: 'tcp', 17: 'udp', 1: 'icmpv4', 58: 'icmpv6', 132: 'sctp'}

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


def convert_from_ofctl(ofctl, validate=False):
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
    if result.get('eth_type') == _ETHTYPE_ARP:
        _map_arp_fields(result)
    if validate:
        _validate_ofctl(result)
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


def _map_arp_fields(ofctl):
    """Translate nw_src/ipv4_src and nw_dst/ipv4_dst in the special case of
    an ARP match.

    At the point this function is called, nw_src/nw_dst has already been
    renamed to ipv4_src/ipv4_dst.
    """
    if 'ipv4_src' in ofctl and 'arp_spa' not in ofctl:
        ofctl['arp_spa'] = ofctl.pop('ipv4_src')
    if 'ipv4_dst' in ofctl and 'arp_tpa' not in ofctl:
        ofctl['arp_tpa'] = ofctl.pop('ipv4_dst')


def _validate_ofctl(ofctl):
    """Validate the ofctl input.

    1. Each field has the appropriate type/syntax.
    2. There are no unrecognized fields.

    This function does not modify the input.
    """
    for key, value in ofctl.items():
        valid_fn = _VALID_FIELDS.get(key)
        if not valid_fn:
            raise ValueError(
                'validate_ofctl: "%s" is not a valid field name' % key)
        if not valid_fn(value):
            raise ValueError('validate_ofctl: field "%s: %s" is not valid' %
                             (key, value))


def _valid_port_no(value):
    return True


def _valid_int(value):
    try:
        int(str(value), 0)
    except ValueError:
        return False
    return True


def _valid_int_mask(value):
    if isinstance(value, str) and '/' in value:
        value, mask = value.split('/', 1)
        return _valid_int(value) and _valid_int(mask)
    return _valid_int(value)


def _valid_macaddr(value):
    return True


def _valid_ipv4(value):
    return True


def _valid_ipv6(value):
    return True


def _valid_vlan(value):
    return _valid_int_mask(value)


_VALID_FIELDS = {
    'in_port': _valid_port_no,
    'in_phy_port': _valid_int,
    'metadata': _valid_int_mask,
    'eth_dst': _valid_macaddr,
    'eth_src': _valid_macaddr,
    'eth_type': _valid_int,
    'vlan_vid': _valid_vlan,
    'vlan_pcp': _valid_int,
    'ip_dscp': _valid_int,
    'ip_ecn': _valid_int,
    'ip_proto': _valid_int,
    'ipv4_src': _valid_ipv4,
    'ipv4_dst': _valid_ipv4,
    'tcp_src': _valid_int_mask,
    'tcp_dst': _valid_int_mask,
    'udp_src': _valid_int_mask,
    'udp_dst': _valid_int_mask,
    'sctp_src': _valid_int_mask,
    'sctp_dst': _valid_int_mask,
    'icmpv4_type': _valid_int,
    'icmpv4_code': _valid_int,
    'arp_op': _valid_int,
    'arp_spa': _valid_ipv4,
    'arp_tpa': _valid_ipv4,
    'arp_sha': _valid_macaddr,
    'arp_tha': _valid_macaddr,
    'ipv6_src': _valid_ipv6,
    'ipv6_dst': _valid_ipv6,
    'ipv6_flabel': _valid_int,
    'icmpv6_type': _valid_int,
    'icmpv6_code': _valid_int,
    'ipv6_nd_target': _valid_ipv6,
    'ipv6_nd_sll': _valid_macaddr,
    'ipv6_nd_tll': _valid_macaddr,
    'mpls_label': _valid_int,
    'mpls_tc': _valid_int,
    'mpls_bos': _valid_int,
    'pbb_isid': _valid_int_mask,
    'tunnel_id': _valid_int_mask,
    'ipv6_exthdr': _valid_int_mask,
    'pbb_uca': _valid_int,
}
