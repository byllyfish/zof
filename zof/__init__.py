"""zof framework."""

__version__ = '0.50.0'

import sys
if sys.version_info < (3, 6):  # pragma: no cover
    import platform
    raise NotImplementedError(
        'zof does not support Python %s. Python 3.6 required.' %
        platform.python_version())

# pylint: disable=wrong-import-position

from zof.controller import Controller, get_controller  # noqa: E402
from zof.configuration import Configuration  # noqa: E402
from zof.datapath import Datapath  # noqa: E402
from zof.driver import Driver  # noqa: E402
from zof.exception import RequestError  # noqa: E402
from zof.match import Match  # noqa: E402
from zof.packet import Packet  # noqa: E402
