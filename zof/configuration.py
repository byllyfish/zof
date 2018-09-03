"""Configuration object for Controller."""

import signal

from zof.driver import Driver


class Configuration:
    """Stores Controller settings."""

    #: Default driver class.
    zof_driver_class = Driver

    #: Default exit signals.
    exit_signals = [signal.SIGTERM, signal.SIGINT]

    #: List of endpoints to listen for OpenFlow connections "host:port".
    listen_endpoints = ['6653']

    #: List of acceptable OpenFlow versions.
    listen_versions = [4]

    #: TLS certificate authority.
    tls_cacert = ''

    #: TLS certificate chain.
    tls_cert = ''

    #: TLS key log file.
    tls_keylog = ''

    #: TLS private key.
    tls_privkey = ''

    def __init__(self, **kwds):
        """Initialize settings by overriding defaults."""
        assert all(hasattr(self, key) for key in kwds)
        self.__dict__.update(kwds)
