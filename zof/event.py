from .objectview import ObjectView, to_json, from_json
from .pktview import pktview_from_list


class Event(ObjectView):
    """Concrete class that represents an Event."""

    def __init__(self, d):
        super().__init__(d)
        try:
            # Any value with key 'data' MUST be a binary type.
            # If there's no `data` key, the rest of this is skipped.
            self.data = bytes.fromhex(d['data'])
            # If there's no `_pkt` key, the rest is skipped.
            self.pkt = pktview_from_list(d['_pkt'])
            del d['_pkt']
            # If there's no 'x_pkt_pos' key in self.pkt, the rest is skipped.
            self.pkt.payload = self.data[self.pkt['x_pkt_pos']:]
        except KeyError:
            pass


def load_event(event):
    try:
        return from_json(event, object_hook=Event)
    except ValueError as ex:
        # Report malformed JSON input.
        return make_event(event='EXCEPTION', reason=str(ex), input=event)


def dump_event(event):
    if isinstance(event, str):
        return event.encode('utf-8')
    return to_json(event).encode('utf-8')


def make_event(**kwds):
    if not kwds:
        raise ValueError('Missing event arguments')
    return _make_event(kwds)


def _make_event(obj):
    for key in obj:
        if isinstance(obj[key], dict):
            obj[key] = _make_event(obj[key])
    return Event(obj)
