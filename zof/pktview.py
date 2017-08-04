import ipaddress
from .objectview import ObjectView
from .ofctl import convert_from_ofctl

# Reserved payload field.
PAYLOAD = 'payload'


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


def _description(pkt):
    """Return description of packet."""
    # pylint: disable=too-many-return-statements,too-many-branches
    eth_type = pkt('eth_type')
    if eth_type == 0x0806:
        arp_op = pkt('arp_op')
        if arp_op == 1:
            return 'ARP:REQ'
        if arp_op == 2:
            return 'ARP:REPLY'
        return 'ARP:%s' % arp_op
    if eth_type == 0x0800:
        ip_proto = pkt('ip_proto')
        if ip_proto == 1:
            return 'ICMPv4'
        if ip_proto == 2:
            return 'IGMPv4'
        if ip_proto == 6:
            return 'TCPv4'
        if ip_proto == 17:
            return 'UDPv4'
        return 'IPv4:%s' % ip_proto
    if eth_type == 0x86dd:
        ip_proto = pkt('ip_proto')
        if ip_proto == 58:
            return 'ICMPv6'
        if ip_proto == 6:
            return 'TCPv6'
        if ip_proto == 17:
            return 'UDPv6'
        return 'IPv6:%s' % ip_proto
    if eth_type == 0x88cc:
        return 'LLDP'
    return 'ETH:%s' % eth_type


class PktView(ObjectView):
    """Concrete class that represents a packet's header fields and payload.

    Use `make_pktview()` to construct a PktView object. The framework client may
    use a custom PktView subclass to add extra features.
    """

    # Alias some packet fields.
    ip_ttl = pktview_alias('nx_ip_ttl')
    hop_limit = pktview_alias('nx_ip_ttl')
    ipv6_nd_res = pktview_alias('x_ipv6_nd_res')

    def items(self):
        return self.__dict__.items()

    def get_description(self):
        return _description(self)

    PROTO_FIELD = {
        'ETHERNET': 'eth_type',
        'ARP': 'arp_op',
        'IPV4': 'ipv4_src',
        'IPV6': 'ipv6_src',
        'ICMPV4': 'icmpv4_type',
        'ICMPV6': 'icmpv6_type'
    }

    def get_protocol(self, protocol):
        """Check if pkt is of specified type and return `self`.

        Return None if pkt does not match specified protocol name. This API is
        intended to be similar to RYU's. The implementation is not intended to
        exhaustively check every field; the oftr tool is reponsible for
        populating all necessary protocol fields.
        """
        return self if PktView.PROTO_FIELD[protocol.upper()] in self else None


def make_pktview(**kwds):
    """Construct a new PktView object."""
    return PktView(kwds)


def pktview_from_list(fields, *, slash_notation=False):
    """Construct a PktView object from a list of field objects.

    A field object may be an ObjectView or a dict.

    Args:
        fields (Seq[ObjectView|dict]): Sequence of fields.
        slash_notation (bool): If true, convert to "value/mask" notation.
    """
    if not isinstance(fields, (list, tuple)):
        raise ValueError('Expected list or tuple')

    pkt = make_pktview()
    for field in fields:
        key = field['field'].lower()
        if key == PAYLOAD:
            raise ValueError('Field "payload" is reserved')
        if 'mask' in field:
            value = (field['value'], field['mask'])
            if slash_notation:
                value = '%s/%s' % value
        else:
            value = field['value']
        pkt[key] = value
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

    return PktView(convert_from_ofctl(ofctl))


def _make_field(name, value):
    fname = name.upper()
    if fname in _SLASH_FIELDS:
        value = convert_slash_notation(fname, value)

    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError('len(tuple) != 2')
        return dict(field=fname, value=value[0], mask=value[1])

    return dict(field=fname, value=value)


def _iter_items(obj):
    if isinstance(obj, dict):
        return obj.items()
    return obj.__dict__.items()


def convert_slash_notation(fname, value):
    """Convert string value in slash notation into a tuple (addr, mask).
    """
    assert fname.isupper()
    if not isinstance(value, str) or '/' not in value:
        return value

    if fname in _MAC_FIELDS:
        return tuple(value.split('/', 1))

    try:
        # ip_interface handles IP prefix notation "/nn"
        addr = ipaddress.ip_interface(value)
        return (addr.ip, addr.netmask)
    except ValueError:
        if not fname.startswith('IPV6_'):
            raise

    # Handle generic slash notation for IPv6 addresses.
    addr = value.split('/', 1)
    return (ipaddress.IPv6Address(addr[0]), ipaddress.IPv6Address(addr[1]))


_MAC_FIELDS = {'ETH_DST', 'ETH_SRC', 'ARP_SHA', 'ARP_THA'}
_SLASH_FIELDS = {'IPV4_SRC', 'IPV4_DST', 'IPV6_SRC', 'IPV6_DST'} | _MAC_FIELDS
