from .objectview import ObjectView


class PktDecode(ObjectView):
    """Concrete class that represents a PktDecode.
    """

    def __init__(self, fields):
        assert isinstance(fields, (list, tuple))
        super().__init__({})
        for field in fields:
            key = field['field'].lower()
            assert key != 'payload'
            self.__dict__[key] = field['value']

    @staticmethod
    def to_list(obj):
        return [dict(field=k.upper(), value=v) for k, v in obj.items() if k != 'payload']
