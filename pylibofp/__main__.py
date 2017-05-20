import argparse

from .ofp_app import ofp_run
from .ofp_args import import_module


def main():
    args = parse_args()
    for module in args.modules:
        import_module(module)
    ofp_run()


def parse_args():
    parser = argparse.ArgumentParser(
        prog='ofp_app',
        description='ofp_app runner',
        epilog='(M) indicates an option may appear more than once\n')
    parser.add_argument(
        '--shell', action='store_true', help='use command shell')
    parser.add_argument(
        '--listen',
        action='append',
        default=['6653'],
        help='listen endpoint [addr:]port (M)')
    parser.add_argument('--loglevel', default='INFO', help='log level')
    parser.add_argument('--logfile', default=None, help='log file')
    parser.add_argument('modules', metavar='module', type=str, nargs='+', help='modules to import')
    return parser.parse_args()


if __name__ == '__main__':
    main()

