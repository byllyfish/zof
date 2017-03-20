from .objectview import ObjectView
import ipaddress

# Reserved payload field.
PAYLOAD = 'payload'


def _alias_property(name):
    def fget(self):
        return self.__dict__[name]
    def fset(self, value):
        self.__dict__[name] = value
    def fdel(self):
        del self.__dict__[name]
    return property(fget=fget, fset=fset, fdel=fdel)



class PktView(ObjectView):
    """Concrete class that represents a packet's header fields and payload."""

    def __init__(self):
        super().__init__({})

    hoplimit = _alias_property('nx_ip_ttl')


def pktview_from_list(fields):
    """Construct a PktView object from a list of field objects.

    A field object may be an ObjectView or a dict.
    """
    if not isinstance(fields, (list, tuple)):
        raise ValueError('Expected list or tuple')

    pkt = PktView()
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
    """Convert a PktView object (or dict) into a list of fields.
    """
    if not isinstance(pkt, (dict, ObjectView)):
        raise ValueError('Expected a dict or ObjectView')

    return [_make_field(k, v) for k, v in _iter_items(pkt) if k != PAYLOAD]


def pktview_from_ofctl(ofctl):
    """Convert an 'ofctl' dict to a PktView object."""
    if not isinstance(ofctl, dict):
        raise ValueError('Expected a dict')

    pkt = PktView()
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
    legacy_fields = dict(dl_type='eth_type', dl_src='eth_src', dl_dst='eth_dst', dl_vlan='vlan_vid', nw_src='ipv4_src', nw_dst='ipv4_dst', nw_proto='ip_proto')
    return legacy_fields.get(key, key)


def _convert_slash_notation(value):
    if not isinstance(value, str):
        return value
    if '/' not in value:
        return value
    addr = ipaddress.ip_interface(value)
    return (addr.ip, addr.netmask)


