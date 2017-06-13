__version__ = '0.1.0'

import sys
if sys.version_info[:3] < (3, 5, 1):
    import platform
    raise NotImplementedError('Python %s is not supported by the ofp_app framework. Python 3.5.1 or later required.' % platform.python_version())

from .ofp_app import ofp_app, ofp_run
from .ofp_args import ofp_common_args
from .ofp_compile import ofp_compile

__all__ = ['ofp_app', 'ofp_compile', 'ofp_run', 'ofp_common_args']
