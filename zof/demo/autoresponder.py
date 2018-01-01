import zof

APP = zof.Application('autoresponder')


@APP.event('start')
def start(_):
    # Only set up the filter once for all datapaths.
    _SET_FILTER.send()


@APP.message('channel_up')
def channel_up(_):
    _DELETE_FLOWS.send()
    _DELETE_GROUPS.send()
    _BARRIER.send()
    _TABLE_MISS.send()
    _ARP_HUB.send()
    _ECHO_REPLY_GROUP.send()
    _ECHO_REPLY.send()


@APP.message('packet_in')
def packet_in(event):
    APP.logger.info('packet_in: %r', event['msg']['pkt'])


_SET_FILTER = zof.compile({
    'method':
    'OFP.SET_FILTER',
    'params': [{
        'filter': 'icmp',
        'action': 'GENERIC_REPLY'
    }]
})

_DELETE_FLOWS = zof.compile('''
    type: FLOW_MOD
    msg:
      command: DELETE
      table_id: ALL
''')

_TABLE_MISS = zof.compile('''
    type: FLOW_MOD
    msg:
      command: ADD
      table_id: 0
      instructions:
        - instruction: APPLY_ACTIONS
          actions:
            - action: OUTPUT
              port_no: CONTROLLER
''')

_ARP_HUB = zof.compile('''
    type: FLOW_MOD
    msg:
      command: ADD
      table_id: 0
      priority: 1
      match:
        - field: ETH_TYPE
          value: 0x0806   # ARP
      instructions:
        - instruction: APPLY_ACTIONS
          actions:
            - action: OUTPUT
              port_no: ALL
''')

_BARRIER = zof.compile('''
    type: BARRIER_REQUEST
''')

_DELETE_GROUPS = zof.compile('''
    type: GROUP_MOD
    msg:
      command: DELETE
      type: ALL
      group_id: ALL
      buckets: []
''')

_ECHO_REPLY_GROUP = zof.compile('''
    type: GROUP_MOD
    msg:
      command: ADD
      type: ALL
      group_id: 1000
      buckets:
        - actions:
          - action: NX_REG_MOVE
            src: IPV4_DST
            dst: PKT_REG0
          - action: NX_REG_MOVE
            src: IPV4_SRC
            dst: IPV4_DST
          - action: NX_REG_MOVE
            src: PKT_REG0[0:32]
            dst: IPV4_SRC
          - action: SET_FIELD
            field: ICMPV4_TYPE
            value: 0
          - action: NX_REG_MOVE
            src: ETH_SRC
            dst: PKT_REG0[0:48]
          - action: NX_REG_MOVE
            src: ETH_DST
            dst: ETH_SRC
          - action: NX_REG_MOVE
            src: PKT_REG0[0:48]
            dst: ETH_DST
          - action: OUTPUT
            port_no: IN_PORT
''')

_ECHO_REPLY = zof.compile('''
    type: FLOW_MOD
    msg:
      command: ADD
      table_id: 0
      priority: 2
      match: 
        - field: IPV4_DST
          value: 10.0.0.1
        - field: ICMPV4_TYPE
          value: 8
      instructions:
        - instruction: APPLY_ACTIONS
          actions:
            - action: GROUP
              group_id: 1000
''')

if __name__ == '__main__':
    zof.run()
