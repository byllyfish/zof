import collections
import logging


class TailBufferedHandler(logging.Handler):
    """Logging handler that records the last N log records.
    """
    singleton = None

    def __init__(self, maxlen=10):
        super().__init__()
        self._tail = collections.deque(maxlen=maxlen)

    def lines(self):
        """Generator for last N log lines.
        """
        for record in self._tail:
            try:
                yield self.format(record)
            except Exception:
                self.handleError(record)

    def emit(self, record):
        self._tail.append(record)

    def close(self):
        super().close()
        self._tail.clear()


    @staticmethod
    def install():
        """Install tail logging handler.
        """
        # Only install it once.
        if TailBufferedHandler.singleton:
            return
        handler = TailBufferedHandler()
        root_logger = logging.getLogger()
        handler.setFormatter(root_logger.handlers[0].formatter)
        root_logger.addHandler(handler)
        TailBufferedHandler.singleton = handler

    @staticmethod
    def tail():
        """Return last N lines.
        """
        return TailBufferedHandler.singleton.lines()
