"""Implements Packet class."""


class Packet(dict):
    """Packet implementation."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__  # type: ignore

    @classmethod
    def from_field_list(cls, fields):
        """Construct a Packet from a list of fields.

        Args:
            fields (List[dict]): Sequence of fields.
        """
        assert isinstance(fields, list)

        pkt = cls()
        for field in fields:
            key = field['field'].lower()
            value = field['value']
            if key in pkt:
                orig_value = pkt[key]
                if isinstance(orig_value, list):
                    orig_value.append(value)
                else:
                    pkt[key] = [orig_value, value]
            else:
                pkt[key] = value
        return pkt

    def to_field_list(self):
        """Return as list of fields."""
        result = []
        for key, value in self.items():
            if isinstance(value, list):
                for repeated_value in value:
                    result.append({'field': key.upper(),
                                   'value': repeated_value})
            else:
                result.append({'field': key.upper(), 'value': value})
        return result
