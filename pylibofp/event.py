import json
from pylibofp.objectview import ObjectView, to_json


class Event(ObjectView):
    """
    Concrete class that represents an Event.
    """

    def __init__(self, d):
        super().__init__(d)
        try:
            self.data = bytes.fromhex(d['data'])
            self.pkt = MatchObject(d['_pkt_decode'])
            del d['_pkt_decode']
        except KeyError:
            pass


class MatchObject(ObjectView):
    """
    Concrete class that represents a Match with convenient accessors.
    """

    def __init__(self, match):
        super().__init__({})
        for field in match:
            self.__dict__[field.field.lower()] = field.value


def load_event(event):
    # If `event` is a byte string, decode it as utf-8.
    if isinstance(event, bytes):
        event = event.decode('utf-8')
    try:
        return json.loads(event, object_hook=Event)
    except ValueError as ex:
        # Report malformed JSON input.
        return make_event(event='EXCEPTION', reason=str(ex), input=event)


def dump_event(event):
    return to_json(event).encode('utf-8') + b'\n'


def make_event(**kwds):
    return _make_event(kwds)


def _make_event(obj):
    for key in obj:
        if isinstance(obj[key], dict):
            obj[key] = _make_event(obj[key])
    return Event(obj)
