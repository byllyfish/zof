import argparse

from pylibofp import ofp_run
from . import layer2


def main():
    args = parse_args()
    if args.shell:
        from pylibofp.service.command_shell import app
        app.command_prompt = 'layer2> '
    ofp_run(listen_endpoints=args.listen, loglevel=args.loglevel, logfile=args.logfile)


def parse_args():
    parser = argparse.ArgumentParser(prog='layer2', description='Layer2 Controller Demo', epilog='(M) indicates an option may appear more than once\n')
    parser.add_argument('--shell', action='store_true', help='use command shell')
    parser.add_argument('--listen', action='append', default=['6653'], help='listen endpoint [addr:]port (M)')
    parser.add_argument('--loglevel', default='INFO', help='log level')
    parser.add_argument('--logfile', default=None, help='log file')
    return parser.parse_args()    


if __name__ == '__main__':
    main()
