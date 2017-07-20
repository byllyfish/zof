import argparse
import importlib
import sys
from .controller import Controller
from .logging import EXT_STDERR

DEFAULT_ENDPOINTS = [6633, 6653]
DEFAULT_LOGFILE = EXT_STDERR
DEFAULT_LOGLEVEL = 'info'


class _SplitCommaAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError('nargs not allowed')
        super().__init__(option_strings, dest, **kwargs)
        self._count = 0

    def __call__(self, parser, namespace, values, option_string=None):
        self._count += 1
        if self._count > 1:
            raise argparse.ArgumentError(self, 'Option present more than once')
        values = [s.strip() for s in values.split(',')]
        setattr(namespace, self.dest, values)


class _ArgParserTest(argparse.ArgumentParser):
    """ArgumentParser subclass that does not exit.
    """
    def exit(self, status=0, message=None):
        raise RuntimeError('_ArgParserTest: status=%d, message="%s"' % (status, message))


def _parent_args():
    return [app.arg_parser for app in Controller.singleton().apps if app.arg_parser is not None]


def common_args(*, under_test=False):
    """Construct default ArgumentParser parent.

    Args:
        under_test (Boolean): When true, create an argument parser subclass
            that raises an exception instead of calling exit.
    """
    parser_class = _ArgParserTest if under_test else argparse.ArgumentParser
    parser = parser_class(add_help=False, parents=_parent_args())

    log_group = parser.add_argument_group('log arguments')
    log_group.add_argument('--loglevel', metavar='LEVEL', help='log level', default=DEFAULT_LOGLEVEL)
    log_group.add_argument('--logfile', metavar='FILE', help='log file', default=DEFAULT_LOGFILE)

    listen_group = parser.add_argument_group('listen arguments')
    listen_group.add_argument(
        '--listen-endpoints',
        metavar='ENDPOINT,...',
        action=_SplitCommaAction,
        help='listen endpoints separated by commas',
        default=DEFAULT_ENDPOINTS)
    listen_group.add_argument('--listen-versions', metavar='VERSION,...', action=_SplitCommaAction, help='listen versions (1-6) separated by commas')
    listen_group.add_argument(
        '--listen-cert', type=file_content, metavar='FILE', help='certificate chain')
    listen_group.add_argument(
        '--listen-cacert',
        type=file_content,
        metavar='FILE',
        help='certificate authority')
    listen_group.add_argument(
        '--listen-privkey', type=file_content, metavar='FILE', help='private key')

    x_group = parser.add_argument_group('experimental')
    x_group.add_argument('--x-modules', metavar='MODULE,...', action=_SplitCommaAction, help='modules to import')
    x_group.add_argument('--x-uvloop', action='store_true', help='use uvloop')
    x_group.add_argument('--x-oftr-path', help='path to oftr executable')
    x_group.add_argument('--x-oftr-args', help='arguments passed to oftr')
    x_group.add_argument('--x-oftr-prefix', help='prefix used to launch oftr (valgrind, strace, catchsegv)')
    x_group.add_argument('--x-under-test', action='store_true', default=under_test, help='special test mode')

    return parser


def import_modules(modules):
    """Import modules."""
    try:
        for module in modules:
            importlib.import_module(module)
    except ImportError as ex:
        print(ex, file=sys.stderr, flush=True)
        sys.exit(1)


def file_content(filename):
    """Return content of string as file."""
    with open(filename, encoding='utf-8') as afile:
        return afile.read()
