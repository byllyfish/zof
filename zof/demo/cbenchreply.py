import zof

APP = zof.Application('cbenchreply')

FLOW_MOD = zof.compile('''
type: FLOW_MOD
flags: [NO_ALERT]
msg:
  table_id: 0
  command: ADD
  match:
   - field: ETH_DST
     value: $eth_dst
''')


@APP.message('packet_in')
def packet_in(event):
    FLOW_MOD.send(eth_dst=event['msg']['pkt'].eth_dst)


if __name__ == '__main__':
    zof.run()
