import asyncio
import argparse
import zof


def _arg_parser():
    parser = argparse.ArgumentParser(
        prog='conntest', description='Connection Closer', add_help=False)
    parser.add_argument(
        '--close-interval',
        type=int,
        default=1,
        help='Interval at which to close connections (seconds)')
    parser.add_argument(
        '--close-all', action='store_true', help='Close all connections')
    return parser


APP = zof.Application(
    'conntest', exception_fatal=True, arg_parser=_arg_parser())


@APP.event('start')
async def start(_):
    while True:
        await asyncio.sleep(APP.args.close_interval)
        # Obtain a list of all connections.
        conns = await zof.get_connections()
        for conn in conns:
            # If the connection has an associated datapath_id, close it.
            if conn['datapath_id'] or APP.args.close_all:
                APP.logger.info('close %d %s', conn['conn_id'],
                                conn['datapath_id'])
                count = await zof.close(conn_id=conn['conn_id'])
                assert count <= 1


if __name__ == '__main__':
    zof.run()
