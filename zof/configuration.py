"""Configuration object for Controller."""

import signal

from zof.driver import Driver


class Configuration:
    """Stores Controller settings.

    Attributes:
        exit_signals (List[Signal]): Unix signals that will exit the controller.
        listen_endpoints (List[str]): List of endpoints to listen for OpenFlow connections.
        listen_versions (List[int]): List of acceptable OpenFlow versions.
        tls_cacert (str): TLS certificate authority.
        tls_cert (str): TLS certificate chain.
        tls_keylog (str): TLS key log file.
        tls_privkey (str): TLS private key.
    """

    zof_driver_class = Driver
    exit_signals = [signal.SIGTERM, signal.SIGINT]
    listen_endpoints = ['6653']
    listen_versions = [4]
    tls_cacert = ''
    tls_cert = ''
    tls_keylog = ''
    tls_privkey = ''

    def __init__(self, **kwds):
        """Initialize settings by overriding defaults."""
        assert all(hasattr(self, key) for key in kwds)
        self.__dict__.update(kwds)
