import asyncio
import zof
from zof.demo.simulator import APP as SIM

APP = zof.Application('zbench', exception_fatal=True)

APP.flowmod_count = 0
APP.packetout_count = 0
APP.packetin_count = 0


@APP.event('start')
async def start(event):
    await asyncio.sleep(1)
    APP.flowmod_count = 0
    run_zbench()
    while True:
        await asyncio.sleep(0.25)
        APP.logger.info('%d packetin, %d flowmod, %d packetout',
                        APP.packetin_count, APP.flowmod_count,
                        APP.packetout_count)
        #if APP.flowmod_count and APP.flowmod_count >= APP.packetin_count:
        #    break


@APP.message('flow_mod', datapath_id=None)
def flowmod(event):
    #APP.logger.info('flowmod: %r', event)
    APP.flowmod_count += 1


@APP.message('packet_out', datapath_id=None)
def packet_out(event):
    APP.packetout_count += 1


@APP.message('packet_in')
def packet_in(event):
    APP.packetin_count += 1


PACKET_IN = zof.compile('''
type:            PACKET_IN
msg:             
  buffer_id:       NO_BUFFER
  total_len:       0x002E
  in_port:         0x00000002
  in_phy_port:     0x00000002
  metadata:        0x0000000000000000
  reason:          APPLY_ACTION
  table_id:        0x03
  cookie:          0x000000005ADC15C0
  match:           
    - field:       IN_PORT
      value:       0x00000002
  data:            B21F7DA0EBDB9EF45FA6B15781000064080600010800060400029EF45FA6B1570A000002B21F7DA0EBDB0A000001
''')


def run_zbench():
    for conn_id in SIM.conn_to_sim:
        APP.logger.info('Send packet_ins to conn_id %s', conn_id)
        for _ in range(1000):
            PACKET_IN.send(conn_id=conn_id)


if __name__ == '__main__':
    zof.run()
