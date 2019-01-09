"""Common utility functions."""

import json


_ENCODER = json.JSONEncoder(ensure_ascii=False, separators=(',', ':'))


def from_json(value):
    """Deserialize JSON value."""
    return json.loads(value)


def to_json(value):
    """Serialize value to JSON."""
    return _ENCODER.encode(value)
