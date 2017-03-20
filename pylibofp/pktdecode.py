from .objectview import ObjectView, item_iter


class PktDecode(ObjectView):
    """Concrete class that represents a decoded packet."""

    def __init__(self, fields):
        super().__init__({})

        if not isinstance(fields, (list, tuple)):
            raise ValueError('Expected list or tuple')
        
        for field in fields:
            key = field['field'].lower()
            assert key != 'payload'
            self.__dict__[key] = field['value']

    @staticmethod
    def to_list(obj):
        """Convert decoded packet to a list of fields."""
        return [_make_field(k, v) for k, v in item_iter(obj) if k != 'payload']


def _make_field(name, value):
    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError('len(tuple) != 2')
        return dict(field=name.upper(), value=value[0], mask=value[1])
    return dict(field=name.upper(), value=value)
