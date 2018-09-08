"""zof framework."""

__version__ = '0.99.0'

import sys
if sys.version_info[:2] < (3, 7):
    import platform
    raise NotImplementedError(
        'zof does not support Python %s. Python 3.7 required.'
        % platform.python_version())

from zof.controller import Controller  # noqa: E402
from zof.configuration import Configuration  # noqa: E402
from zof.datapath import Datapath  # noqa: E402
from zof.driver import Driver  # noqa: E402
from zof.exception import RequestError  # noqa: E402
from zof.packet import Packet  # noqa: E402
