from pylibofp import ofp_compile


delete_flows = ofp_compile('''
  # Delete flows in table 0.
  type: FLOW_MOD
  msg:
    command: DELETE
    table_id: 0
''')


barrier = ofp_compile('''
  type: BARRIER_REQUEST
''')


table_miss_flow = ofp_compile('''
  # Add permanent table miss flow entry to table 0
  type: FLOW_MOD
  msg:
    command: ADD
    table_id: 0
    priority: 0
    instructions:
      - instruction: APPLY_ACTIONS
        actions:
          - action: OUTPUT
            port_no: CONTROLLER
            max_len: NO_BUFFER
''')


learn_mac_flow = ofp_compile('''
  type: FLOW_MOD
  msg:
    table_id: 0
    command: ADD
    idle_timeout: 30
    hard_timeout: 0
    priority: 10
    buffer_id: NO_BUFFER
    flags: [ SEND_FLOW_REM ]
    match:
      - field: IN_PORT
        value: $in_port
      - field: ETH_DST
        value: $eth_dst
      - field: VLAN_VID
        value: $vlan_vid
    instructions:
      - instruction: APPLY_ACTIONS
        actions:
          - action: OUTPUT
            port_no: $out_port
            max_len: MAX
''')


packet_out = ofp_compile('''
  type: PACKET_OUT
  msg:
    actions: 
      - action: OUTPUT
        port_no: $out_port
        max_len: MAX
    data: $data
''')


packet_flood = ofp_compile('''
  type: PACKET_OUT
  msg:
    in_port: $in_port
    actions: 
      - action: OUTPUT
        port_no: ALL
        max_len: MAX
    data: $data
''')


