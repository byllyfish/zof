import argparse

from pylibofp import ofp_run, ofp_default_args
from . import layer2


def main():
    args = parse_args()
    if args.shell:
        import pylibofp.service.command_shell as cmd_shell
        cmd_shell.app.command_prompt = 'layer2> '
    ofp_run(args=args)


def parse_args():
    parser = argparse.ArgumentParser(
        prog='layer2',
        description='Layer2 Demo',
        parents=[ofp_default_args()])
    parser.add_argument(
        '--shell', action='store_true', help='use command shell')
    return parser.parse_args()


if __name__ == '__main__':
    main()
