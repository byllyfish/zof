"""Configuration object for Controller."""

import signal

from zof.driver import Driver


class Configuration:
    """Stores Controller settings."""

    #: List of endpoints to listen for OpenFlow connections "host:port".
    listen_endpoints = ['6653']

    #: Listen options for oftr.
    listen_options = ['FEATURES_REQ']

    #: List of supported OpenFlow versions.
    listen_versions = [4]

    #: Default exit signals.
    exit_signals = [signal.SIGTERM, signal.SIGINT]

    #: Default driver class.
    driver_class = Driver

    def __init__(self, **kwds):
        """Initialize settings by overriding defaults."""
        assert all(hasattr(self, key) for key in kwds)
        self.__dict__.update(kwds)
