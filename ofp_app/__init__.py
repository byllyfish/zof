__version__ = '0.1.0'

import sys
if sys.version_info[:3] < (3, 5, 1):
    import platform
    raise NotImplementedError(
        'Python %s is not supported by the ofp_app framework. Python 3.5.1 or later required.'
        % platform.python_version())

# pylint: disable=wrong-import-position
from .api_application import Application
from .api_run import run
from .api_args import common_args
from .api_compile import compile

__all__ = ['Application', 'ofp_compile', 'ofp_run', 'ofp_common_args']