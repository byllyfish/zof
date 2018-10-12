"""Configuration object for Controller."""

import signal

from zof.driver import Driver


class Configuration:
    """Stores Controller settings.

    Attributes:
        exit_signals (List[Signal]): Unix signals that will stop the
            controller. Default is [SIGTERM, SIGINT].
        listen_endpoints (List[str]): List of endpoints to listen for OpenFlow
            connections. Default is ['6653'].
        listen_versions (List[int]): List of acceptable OpenFlow versions.
            Default is [1, 4, 5, 6].
        tls_cacert (str): TLS certificate authority. Default is ''.
        tls_cert (str): TLS certificate chain. Default is ''.
        tls_keylog (str): TLS key log file. Default is ''.
        tls_privkey (str): TLS private key. Default is ''.

    """

    zof_driver_class = Driver
    exit_signals = [signal.SIGTERM, signal.SIGINT]
    listen_endpoints = ['6653']
    listen_versions = [1, 4, 5, 6]
    tls_cacert = ''
    tls_cert = ''
    tls_keylog = ''
    tls_privkey = ''

    def __init__(self, **kwds):
        """Initialize settings by overriding defaults."""
        assert all(hasattr(self, key) for key in kwds)
        self.__dict__.update(kwds)
