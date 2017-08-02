import re

_ENDPOINT_REGEX = re.compile(r'^(?:(?:\[(\S*)\]|(\S*)):)?(\d+)$')


class Endpoint:
    def __init__(self, endpt):
        self.host, self.port = self._split(endpt)

    @property
    def pair(self):
        """Return 2-tuple containing host and port."""
        return (self.host, self.port)

    @staticmethod
    def _split(endpt):
        m = _ENDPOINT_REGEX.match(endpt)
        if not m:
            raise ValueError('Invalid endpoint: %s' % endpt)
        return (m.group(1) or m.group(2) or '', int(m.group(3)))

    def __str__(self):
        if ':' in self.host:
            return '[%s]:%u' % self.pair
        return '%s:%d' % self.pair
