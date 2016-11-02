# This is a mock module used by `ControllerAppTestCase` in test_controllerapp.py.

@OFP.channel('all')
def channel_default(event):
    OFP.shared['handler'] = 'channel_default'

@OFP.message('all')
def message_default(event):
    OFP.shared['handler'] = 'message_default'

@OFP.event('all')
def event_default(event):
    OFP.shared['handler'] = 'event_default'

