import zof

APP = zof.Application(__name__)

FLOW_MOD = zof.compile('''
  type: FLOW_MOD
  msg:
    table_id: $table
    command: ADD
    match: []
    instructions:
      - instruction: APPLY_ACTIONS
        actions: 
          - action: OUTPUT
            port_no: $port
''')

@APP.message('CHANNEL_UP')
def channel_up(event):
    FLOW_MOD.send(table=0, port='CONTROLLER')

if __name__ == '__main__':
    zof.run()
