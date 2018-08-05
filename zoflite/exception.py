class RequestError(Exception):
    """Represents a failure of the request() api.

    Attributes:
        message (str): human-readable error message
    """

    def __init__(self, event):
        assert event.get('error') is not None or event.get('type') == 'ERROR'
        super().__init__(event)
        self.message = event['error']['message']
