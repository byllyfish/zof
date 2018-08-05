"""Exception classes."""


class RequestError(Exception):
    """Represents a failure of the request() api.

    Attributes:
        message (str): human-readable error message

    """

    def __init__(self, event):
        """Initialize exception with event."""
        super().__init__(event)
        self.message = event['error']['message']
