import argparse

from pylibofp import ofp_run
from . import layer2

def main():
    parser = argparse.ArgumentParser(description='Layer2 Controller Demo')
    parser.add_argument('--listen', help='Endpoint to listen on (e.g. "6653", "127.0.0.1:6653")')

    args = parser.parse_args()
    print(args)

    ofp_run()
