"""Implements the ObjectView class."""

import json
import io


class ObjectView(object):
    """Wraps a Python dictionary so its attributes can be accessed/assigned
    using dot notation `obj.attr` or `obj['spacey attr']`.

    Examples::

        obj = ObjectView({'get': 42})
        assert obj.get == obj['get'] == 42
        assert obj('to_json', default='foo') == 'foo'
        obj.to_json = 1
        assert obj.to_json == 1

    If you access a value that does not exist, ObjectView raises a KeyError.
    Use callable syntax to access a value using a default if the key is not
    present, e.g. `obj('foo', default='bar')`.

    This class does _not_ recursively wrap sub-objects; it's designed to be
    used as a `json.loads` object_hook.

    This class does not define any non-dunder methods to avoid conflict
    with attribute names.
    """

    def __init__(self, d):
        self.__dict__ = d

    def __contains__(self, key):
        """Make sure that `in` and `not in` still work: `if key in obj:`"""
        return key in self.__dict__

    def __len__(self):
        """Make sure len(obj) works."""
        return len(self.__dict__)

    def __iter__(self):
        """Make sure iteration works."""
        return iter(self.__dict__)

    def __getitem__(self, key):
        """Allow read access using dictionary syntax `obj[key]`."""
        return self.__dict__[key]

    def __setitem__(self, key, value):
        """Allow write access using dictionary syntax `obj[key] = value`."""
        self.__dict__[key] = value

    def __delitem__(self, key):
        """Allow properties to be deleted using dictionary syntax `del obj[key]`."""
        del self.__dict__[key]

    def __call__(self, key, *, default=None):
        """Allow read access using callable syntax `obj(key)`.

        Returns a default (None) if the key is not present.
        """
        try:
            return self.__dict__[key]
        except KeyError:
            return default

    def __eq__(self, obj):
        """Make sure that `==` works as expected."""
        try:
            return self.__dict__ == obj.__dict__
        except AttributeError:
            return self.__dict__ == obj

    def __ne__(self, obj):
        """Make sure that `!=` works as expected."""
        return not self.__eq__(obj)

    def __repr__(self):
        """Return the dictionary representation."""
        return repr(self.__dict__)

    def __str__(self):
        """Return JSON representation."""
        return to_json(self.__dict__)


def to_json(obj):
    """Return string with compact json representation of an object.
    """
    return json.dumps(
        obj,
        separators=(',', ':'),
        ensure_ascii=False,
        default=_json_serialize)


def _json_serialize(obj):
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, ObjectView):
        return obj.__dict__
    if isinstance(obj, io.IOBase):
        return 'file:%s' % obj.name
    try:
        return obj.__getstate__()
    except AttributeError:
        raise TypeError('Value "%s" of type %s is not JSON serializable' %
                        (repr(obj), type(obj)))
