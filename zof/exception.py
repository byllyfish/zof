"""Exception classes."""


class RequestError(Exception):
    """Represents a failure of the request() api.

    Attributes:
        event (dict): event causing failure

    """

    def __init__(self, event):
        """Initialize exception with event."""
        super().__init__(self._extract_message(event))
        self.event = event

    @staticmethod
    def _extract_message(event):
        """Extract message from event."""
        if 'alert' in event:
            # CHANNEL_ALERT reply with xid.
            assert event['type'] == 'CHANNEL_ALERT'
            assert 'xid' in event
            return 'ERROR: %s' % event['alert']
        if 'error' in event:
            # RPC error reply with id.
            assert 'id' in event
            return 'ERROR: %s' % event['error']['message']
        return 'Other event: %r' % event

    @classmethod
    def zof_timeout(cls, xid):
        """Create exception for request timeout."""
        msg = {'id': xid, 'error': {'message': 'request timeout'}}
        return cls(msg)

    @classmethod
    def zof_closed(cls, xid=0):
        """Create exception for closed connection."""
        msg = {'id': xid, 'error': {'message': 'connection closed'}}
        return cls(msg)
