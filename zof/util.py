"""Common utility functions."""

import json
from ipaddress import IPv4Address, IPv6Address


def from_json(value):
    """Deserialize JSON value."""
    return json.loads(value)


def to_json(value):
    """Serialize value to JSON."""
    return json.dumps(
        value,
        separators=(',', ':'),
        ensure_ascii=False,
        default=_json_serialize)


def _json_serialize(value):
    """Support JSON serialization for common value types."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (IPv4Address, IPv6Address)):
        return str(value)
    raise TypeError('Value "%s" of type %s is not JSON serializable' %
                    (repr(value), type(value)))
