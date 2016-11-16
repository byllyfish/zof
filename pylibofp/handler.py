import inspect
import logging
import asyncio

LOGGER = logging.getLogger('pylibofp.controller')

_ALL_SUBTYPE = 'ALL'
_MSG_SUBTYPES = ('FEATURES_REQUEST', 'FEATURES_REPLY', 'PACKET_IN',
                 'PORT_STATUS', _ALL_SUBTYPE)


def make_handler(callback, type_, subtype='', options=None):
    """
    Factory function to create appropriate handler.

    Supported types: message, channel, event
    """
    if type_ == 'message':
        return MessageHandler(callback, type_, subtype, options)
    if type_ == 'channel':
        return ChannelHandler(callback, type_, subtype, options)
    if type_ == 'event':
        return EventHandler(callback, type_, subtype, options)
    raise ValueError('make_handler: Unknown handler type: %s' % type_)


class BaseHandler(object):
    def __init__(self, callback, type_, subtype='', options=None):
        self.callback = callback
        self.type = type_
        self.subtype = subtype.upper()
        self.options = options

    def match(self, event):
        raise NotImplementedError("Please implement this method")

    def __call__(self, event):
        if self.match(event):
            self.callback(event)

    def __repr__(self):
        return '%s[%s] %s@%s' % (self.type, self.subtype,
                                 self.callback.__name__, id(self.callback))

    def verify(self):
        if not _verify_callback(self.callback, 1):
            return False
        return True


class ChannelHandler(BaseHandler):
    def match(self, event):
        # Channel handler needs to check for raw channel.
        if 'datapath_id' not in event:
            if 'datapath_id' not in self.options:
                return False
            elif self.options['datapath_id'] is not None:
                return False
        return event.status == self.subtype or self.subtype == _ALL_SUBTYPE

    def verify(self):
        if not _verify_callback(self.callback, 1):
            return False
        return True


class MessageHandler(BaseHandler):
    def match(self, event):
        if not (event.type == self.subtype or self.subtype == _ALL_SUBTYPE):
            return False
        for key, value in self.options.items():
            if not _match_message_event(key, value, event):
                return False
        return True

    def verify(self):
        if not _verify_callback(self.callback, 1):
            return False
        if self.subtype not in _MSG_SUBTYPES:
            LOGGER.warning(
                'Message handler subtype not recognized: %s',
                self.subtype,
                stack_info=True)
        return True


class EventHandler(BaseHandler):
    def match(self, event):
        return event['event'] == self.subtype or self.subtype == _ALL_SUBTYPE

    def verify(self):
        if not _verify_callback(self.callback, 1):
            return False
        return True


def _verify_callback(callback, param_count):
    """
    Make sure callback function is not a co-routine. Make sure
    it has the expected number of positional parameters.
    """
    if not inspect.isfunction(callback):
        LOGGER.error('Callback is not a function: %s', callback)
        return False
    if asyncio.iscoroutinefunction(callback):
        LOGGER.error('Callback must not be a coroutine function: %s', callback)
        return False
    sig = inspect.signature(callback)
    if len(sig.parameters) != param_count:
        LOGGER.error('Callback has unexpected number of parameters: %s',
                     callback)
        return False
    return True


def _match_message_event(key, value, event):
    """
    Return true if `key` and `value` exist within the given message event.
    If the `msg` is a list, check all elements in the list for the given key.
    """
    val = str(value).upper()
    if key in event.msg:
        return str(event.msg[key]).upper() == val
    if 'pkt' in event.msg:
        pkt = event.msg.pkt
        if key in pkt:
            return str(pkt[key]).upper() == val
    return False
