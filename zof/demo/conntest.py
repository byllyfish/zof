import asyncio
import zof

APP = zof.Application('conntest', exception_fatal=True)


@APP.event('start')
async def start(_):
    while True:
        await asyncio.sleep(1)
        # Obtain a list of all connections.
        conns = await zof.get_connections()
        for conn in conns:
            # If the connection has an associated datapath_id, close it.
            if conn.datapath_id:
                APP.logger.info('close %d %s', conn.conn_id, conn.datapath_id)
                count = await zof.close(datapath_id=conn.datapath_id)
                assert count == 1


if __name__ == '__main__':
    zof.run()
