"""Configuration object for Controller."""

from typing import List, Type  # pylint: disable=unused-import

import signal

from zof.driver import Driver


class Configuration:
    """Stores Controller settings.

    Attributes:
        exit_signals (List[Signals]): Unix signals that will stop the
            controller. Default is [signal.SIGTERM, signal.SIGINT].
        listen_endpoints (List[str]): List of endpoints to listen for OpenFlow
            connections. Default is ['6653'].
        listen_versions (List[int]): List of acceptable OpenFlow versions.
            Default is [1, 4, 5, 6].
        tls_cacert (str): TLS certificate authority. Default is ''.
        tls_cert (str): TLS certificate chain. Default is ''.
        tls_keylog (str): TLS key log file. Default is ''.
        tls_privkey (str): TLS private key. Default is ''.

    """

    zof_driver_class = Driver  # type: Type[Driver]
    exit_signals = [signal.SIGTERM, signal.SIGINT]  # type: List[signal.Signals]
    listen_endpoints = ['6653']  # type: List[str]
    listen_versions = [1, 4, 5, 6]  # type: List[int]
    tls_cacert = ''  # type: str
    tls_cert = ''  # type: str
    tls_keylog = ''  # type: str
    tls_privkey = ''  # type: str

    def __init__(self, **kwds):
        """Initialize settings by overriding defaults."""
        assert all(hasattr(self, key) for key in kwds)
        self.__dict__.update(kwds)
