from zoflite.controller import Controller
from zoflite.backport import asyncio_run


class HubProactiveController(Controller):
    """Demo OpenFlow app that implements a proactive hub."""

    def CHANNEL_UP(self, dp, event):
        # Set up default flow table entry.
        action = {'action': 'OUTPUT', 'port_no': 'ALL', 'max_len': 'NO_BUFFER'}
        instruction = {'instruction': 'APPLY_ACTIONS', 'actions': [action]}
        ofmsg = {
            'type': 'FLOW_MOD',
            'msg': {
                'table_id': 0,
                'command': 'ADD',
                'priority': 0,
                'match': [],
                'instructions': [instruction]
            }  
        }
        dp.send(ofmsg)


if __name__ == '__main__':
    asyncio_run(HubProactiveController().run())
