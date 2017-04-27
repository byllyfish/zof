import argparse

from pylibofp import ofp_run
from . import l2_demo


def main():
    args = parse_args()
    command_prompt = 'l2_demo> ' if args.shell else None
    ofp_run(listen_endpoints=args.listen, command_prompt=command_prompt, loglevel=args.loglevel, logfile=args.logfile)


def parse_args():
    parser = argparse.ArgumentParser(prog='l2_demo', description='Layer2 Controller Demo', epilog='(M) indicates an option may appear more than once\n')
    parser.add_argument('--shell', action='store_true', help='use command shell')
    parser.add_argument('--listen', action='append', default=['6653'], help='listen endpoint [addr:]port (M)')
    parser.add_argument('--loglevel', default='INFO', help='log level')
    parser.add_argument('--logfile', default=None, help='log file')
    return parser.parse_args()    
