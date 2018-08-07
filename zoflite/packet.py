"""Implements Packet class."""


class Packet(dict):
    """Packet implementation."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__  # type: ignore

    @classmethod
    def zof_from_field_list(cls, fields):
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

    def zof_to_field_list(self):
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

    @classmethod
    def zof_from_packet_in(cls, event):
        """Convert packet fields and payload into a Packet object."""
        assert event['type'] == 'PACKET_IN'

        msg = event['msg']
        pkt = cls.zof_from_field_list(msg.pop('_pkt', []))
        pkt_pos = pkt.pop('x_pkt_pos', 0)
        pkt['payload'] = bytes.fromhex(msg.pop('data', ''))[pkt_pos:]
        msg['pkt'] = pkt

    @staticmethod
    def zof_to_packet_out(event):
        """Convert Packet object back to packet fields and data."""
        assert event['type'] == 'PACKET_OUT'

        msg = event['msg']
        pkt = msg.pop('pkt', None)
        if pkt is not None:
            payload = pkt.pop('payload', None)
            if payload is not None:
                msg['_pkt_data'] = payload
            msg['_pkt'] = pkt.zof_to_field_list()
