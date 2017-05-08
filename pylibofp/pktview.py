import ipaddress
from .objectview import ObjectView

# Reserved payload field.
PAYLOAD = 'payload'

#pylint: skip-file
# The presence of the pktview_alias function causes pylint to crash(?).


def pktview_alias(name, converter=(lambda x: x)):
    """Construct property that aliases specified attribute.

    converter function should be idempotent.
    """

    def _fget(self):
        try:
            return converter(self.__dict__[name])
        except KeyError:
            raise AttributeError('PktView object has no attribute "%s"' %
                                 name) from None

    def _fset(self, value):
        self.__dict__[name] = value

    def _fdel(self):
        try:
            del self.__dict__[name]
        except KeyError:
            raise AttributeError('PktView object has no attribute "%s"' %
                                 name) from None

    return property(fget=_fget, fset=_fset, fdel=_fdel)


class PktView(ObjectView):
    """Concrete class that represents a packet's header fields and payload.

    Use `make_pktview()` to construct a PktView object. The framework client may
    use a custom PktView subclass to add extra features.
    """

    PKT_TYPES = {0x0806: 'ARP', 0x0800: 'IPV4', 0x86dd: 'IPV6', 0x88cc: 'LLDP'}

    PROTO_FIELD = {
        'ETHERNET': 'eth_type',
        'ARP': 'arp_op',
        'IPV4': 'ipv4_src',
        'IPV6': 'ipv6_src',
        'ICMPV4': 'icmpv4_type',
        'ICMPV6': 'icmpv6_type'
    }

    @property
    def pkt_type(self):
        """Human-readable description of packet type. (read-only)"""
        return PktView.PKT_TYPES.get(self.eth_type, hex(self.eth_type))

    def get_protocol(self, protocol):
        """Check if pkt is of specified type and return `self`.
        
        Return None if pkt does not match specified protocol name. This API is 
        intended to be similar to RYU's. The implementation is not intended to
        exhaustively check every field; the oftr tool is reponsible for 
        populating all necessary protocol fields.
        """
        return self if PktView.PROTO_FIELD[protocol.upper()] in self else None

    # Alias some packet fields.
    ip_ttl = pktview_alias('nx_ip_ttl')
    hop_limit = pktview_alias('nx_ip_ttl')
    ipv6_nd_res = pktview_alias('x_ipv6_nd_res')

    def items(self):
        return self.__dict__.items()


def make_pktview(**kwds):
    """Construct a new PktView object."""
    return PktView(kwds)


def pktview_from_list(fields):
    """Construct a PktView object from a list of field objects.

    A field object may be an ObjectView or a dict.
    """
    if not isinstance(fields, (list, tuple)):
        raise ValueError('Expected list or tuple')

    pkt = make_pktview()
    for field in fields:
        key = field['field'].lower()
        if key == PAYLOAD:
            raise ValueError('Field "payload" is reserved')
        if 'mask' in field:
            pkt[key] = (field['value'], field['mask'])
        else:
            pkt[key] = field['value']
    return pkt


def pktview_to_list(pkt):
    """Convert a PktView object (or dict) into a list of fields."""
    if not isinstance(pkt, (dict, ObjectView)):
        raise ValueError('Expected a dict or ObjectView')

    return [_make_field(k, v) for k, v in _iter_items(pkt) if k != PAYLOAD]


def pktview_from_ofctl(ofctl):
    """Convert an 'ofctl' dict to a PktView object."""
    if not isinstance(ofctl, dict):
        raise ValueError('Expected a dict')

    pkt = make_pktview()
    for key, value in ofctl.items():
        key = _convert_legacy_field(key, ofctl)
        pkt[key] = value
    return pkt


def _make_field(name, value):
    fname = name.upper()
    if fname in {'IPV4_SRC', 'IPV4_DST', 'IPV6_SRC', 'IPV6_DST'}:
        value = _convert_slash_notation(value)

    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError('len(tuple) != 2')
        return dict(field=fname, value=value[0], mask=value[1])

    return dict(field=fname, value=value)


def _iter_items(obj):
    if isinstance(obj, dict):
        return obj.items()
    return obj.__dict__.items()


def _convert_legacy_field(key, ofctl):
    """Convert ofctl legacy field names."""
    legacy_fields = dict(
        dl_type='eth_type',
        dl_src='eth_src',
        dl_dst='eth_dst',
        dl_vlan='vlan_vid',
        nw_src='ipv4_src',
        nw_dst='ipv4_dst',
        nw_proto='ip_proto')
    return legacy_fields.get(key, key)


def _convert_slash_notation(value):
    """Convert string value in slash notation into a tuple (addr, mask)."""
    if not isinstance(value, str):
        return value
    if '/' not in value:
        return value
    addr = ipaddress.ip_interface(value)
    return (addr.ip, addr.netmask)
