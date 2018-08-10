import asyncio
from zoflite.controller import Controller


class HubProactive(Controller):
    """Demo OpenFlow app that implements a proactive hub."""

    def on_channel_up(self, dp, _event):
        # Set up default flow table entry.
        action = {'action': 'OUTPUT', 'port_no': 'ALL'}
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
    asyncio.run(HubProactive().run())  # type: ignore
