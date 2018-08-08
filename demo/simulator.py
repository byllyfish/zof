
import asyncio
from zoflite.driver import Driver
from zoflite.exception import RequestError
from zoflite.backport import asyncio_run


class MySimulator:

    def __init__(self):
        self.controller_endpoint = '127.0.0.1:6653'
        self.dp_count = 5
        self.driver = Driver(debug=True)

    async def run(self):
        async with self.driver:
            # Make `dp_count` independent connections to `controller_endpoint`.
            try:
                coros = [self.driver.connect(self.controller_endpoint) for i in range(self.dp_count)]
                await asyncio.gather(*coros)
                task = asyncio.ensure_future(self._dispatch())
                await asyncio.sleep(30)
            except RequestError as exc:
                print('ERROR: %r' % exc)
            finally:
                task.cancel()

    async def _dispatch(self):
        while True:
            event = await self.driver.event_queue.get()
            msg_type = event['type'].replace('.', '_')
            msg_method = getattr(self, msg_type, None)
            if msg_method:
                msg_method(event)
            else:
                print('other: %r' % event)

    def CHANNEL_UP(self, event):
        asyncio.ensure_future(self.send_packet_in(event['conn_id']))

    async def send_packet_in(self, conn_id):
        while True:
            await asyncio.sleep(3)
            reply = {
                'conn_id': conn_id,
                'xid': 0,
                'type': 'PACKET_IN',
                'msg': {
                    'buffer_id': 'NO_BUFFER',
                    'in_port': 'CONTROLLER',
                    'metadata': 0,
                    'reason': 'APPLY_ACTION',
                    'table_id': 0,
                    'cookie': 0,
                    'total_len': 50,
                    'data': '000102030405060708090A'
                }
            }
            self.driver.send(reply)

    def FEATURES_REQUEST(self, event):
        print('FEATURES_REQUEST!')
        conn_id = event['conn_id']
        xid = event['xid']
        reply = {
            'conn_id': conn_id,
            'xid': xid,
            'type': 'FEATURES_REPLY',
            'msg': {
                'datapath_id': hex(conn_id),
                'n_buffers': 0,
                'n_tables': 254,
                'capabilities': [0],
                'ports': []
            }
        }
        self.driver.send(reply)

    def REQUEST_PORT_DESC(self, event):
        print('PORT_DESC_REQUEST!')
        #print('port_desc', event)
        conn_id = event['conn_id']
        xid = event['xid']
        reply = {
            'conn_id': conn_id,
            'xid': xid,
            'type': 'REPLY.PORT_DESC',
            'msg': [self._portdesc(i) for i in range(1, 5)]
        }
        self.driver.send(reply)


    def REQUEST_DESC(self, event):
        print('DESC_REQUEST')
        conn_id = event['conn_id']
        xid = event['xid']
        reply = {
            'conn_id': conn_id,
            'xid': xid,
            'type': 'REPLY.DESC',
            'msg': {
                'mfr_desc': 'mfr',
                'hw_desc': 'hw',
                'sw_desc': 'sw',
                'dp_desc': 'dp',
                'serial_num': 'sn'
            }
        }
        self.driver.send(reply)        

    @staticmethod
    def _portdesc(port_no):
        macaddr = '%12.12x' % port_no
        return {
            'port_no': port_no,
            'hw_addr': macaddr,
            'name': 'port %d' % port_no,
            'config': [],
            'state': [],
            'ethernet': {
                'curr': [],
                'advertised': [],
                'supported': [],
                'peer': [],
                'curr_speed': 0,
                'max_speed': 0
            }
        }


if __name__ == '__main__':
    asyncio_run(MySimulator().run())
