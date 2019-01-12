"""zof framework."""

__version__ = '0.50.0'

import sys
if sys.version_info < (3, 6):  # pragma: no cover
    import platform
    raise NotImplementedError(
        'zof does not support Python %s. Python 3.6 required.' %
        platform.python_version())

# pylint: disable=wrong-import-position,wildcard-import

from zof.api import *  # noqa: E402
