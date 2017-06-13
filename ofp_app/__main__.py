import argparse

from .ofp_app import ofp_run
from .ofp_args import ofp_common_args, import_module


def main():
    args = parse_args()
    for module in args.modules:
        import_module(module)
    ofp_run(args=args)


def parse_args():
    parser = argparse.ArgumentParser(
        prog='ofp_app',
        description='ofp_app runner', 
        parents=[ofp_common_args()])
    parser.add_argument('modules', metavar='module', type=str, nargs='+', help='modules to import')
    return parser.parse_args()


if __name__ == '__main__':
    main()

