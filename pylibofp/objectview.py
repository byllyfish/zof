import json
import io


class ObjectView(object):
    """
    Simple class to wrap a Python dictionary so its attributes can be accessed
    using dot notation `obj.attr` in addition to dictionary syntax `obj[key]`.
    This class does _not_ recursively wrap sub-objects; it's designed to be
    used as a `json.loads` object_hook.
    """

    def __init__(self, d):
        self.__dict__ = d

    # Make sure that `in` and `not in` still work: `if key in obj:`
    def __contains__(self, key):
        return key in self.__dict__

    # Make sure len(obj) works.
    def __len__(self):
        return len(self.__dict__)

    # Make sure iteration works.
    def __iter__(self):
        return iter(self.__dict__)

    # Allow read access using dictionary syntax `obj[key]`
    def __getitem__(self, key):
        return self.__dict__[key]

    # Allow write access using dictionary syntax `obj[key] = value`
    def __setitem__(self, key, value):
        self.__dict__[key] = value

    # Allow properties to be deleted using dictionary syntax `del obj[key]`
    def __delitem__(self, key):
        del self.__dict__[key]

    # Make sure that `==` works as expected.
    def __eq__(self, obj):
        try:
            return self.__dict__ == obj.__dict__
        except AttributeError:
            return self.__dict__ == obj

    # Make sure that `!=` works as expected.
    def __ne__(self, obj):
        return not self.__eq__(obj)

    # Return the dictionary representation.
    def __repr__(self):
        return repr(self.__dict__)

    # Return JSON representation.
    def __str__(self):
        return ObjectView.json_dumps(self.__dict__)

    @staticmethod
    def json_dumps(obj):
        """ Return string with compact json representation of the object.

        This is a static method so it can replace calls to `json.dumps(obj)`.
        To dump the object itself, call `obj.json_dumps(obj)`.
        """
        return json.dumps(obj, separators=(',', ':'), ensure_ascii=False, default=_json_serialize)


def _json_serialize(obj):
    if isinstance(obj, bytes):
        return obj.hex()
    if isinstance(obj, ObjectView):
        return obj.__dict__
    if isinstance(obj, io.IOBase):
        return 'file:%s' % obj.name
    raise TypeError('Value "%s" of type %s is not JSON serializable' % (repr(obj), type(obj)))
