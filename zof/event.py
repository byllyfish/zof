from .objectview import to_json, from_json


def load_event(event):
    try:
        return from_json(event)
    except ValueError as ex:
        # Report malformed JSON input.
        return {'event': 'EXCEPTION', 'reason': str(ex), 'input': event}


def dump_event(event):
    if isinstance(event, str):
        return event.encode('utf-8')
    return to_json(event).encode('utf-8')
