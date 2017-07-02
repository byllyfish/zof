import asyncio
from .. import Application, ofp_run

app = Application('conntest', kill_on_exception=True)


@app.event('start')
async def start(_):
    while True:
        await asyncio.sleep(1)
        # Obtain a list of connections.
        conns = await app.rpc_call('OFP.LIST_CONNECTIONS', conn_id=0)
        for conn in conns.stats:
            if conn.datapath_id:
                app.logger.info('close %d %s', conn.conn_id, conn.datapath_id)
                result = await app.rpc_call(
                    'OFP.CLOSE', datapath_id=conn.datapath_id)
                assert result.count == 1


if __name__ == '__main__':
    ofp_run()
