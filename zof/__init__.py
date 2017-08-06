import sys
if sys.version_info[:3] < (3, 5, 1):
    import platform
    raise NotImplementedError(
        'Python %s is not supported by the zof framework. Python 3.5.1 or later required.'
        % platform.python_version())

# pylint: disable=wrong-import-position, redefined-builtin
from .api_application import Application  # noqa: E402,F401
from .api_run import run  # noqa: E402,F401
from .api_args import common_args  # noqa: E402,F401
from .api_compile import compile  # noqa: E402,F401
from .api_functions import get_datapaths, post_event, ensure_future, connect, close, get_connections, add_identity

__version__ = '0.1.0'
