import inspect
import logging
import asyncio


LOGGER = logging.getLogger(__package__)

_MSG_SUBTYPES = {
    "CHANNEL_UP", "CHANNEL_DOWN", "CHANNEL_ALERT", "HELLO", "ERROR",
    "ECHO_REQUEST", "ECHO_REPLY", "EXPERIMENTER", "FEATURES_REQUEST",
    "FEATURES_REPLY", "GET_CONFIG_REQUEST", "GET_CONFIG_REPLY", "SET_CONFIG",
    "PACKET_IN", "FLOW_REMOVED", "PORT_STATUS", "PACKET_OUT", "FLOW_MOD",
    "GROUP_MOD", "PORT_MOD", "TABLE_MOD", "REQUEST.DESC", "REQUEST.FLOW",
    "REQUEST.AGGREGATE", "REQUEST.TABLE", "REQUEST.PORT_STATS",
    "REQUEST.QUEUE", "REQUEST.GROUP", "REQUEST.GROUP_DESC",
    "REQUEST.GROUP_FEATURES", "REQUEST.METER", "REQUEST.METER_CONFIG",
    "REQUEST.METER_FEATURES", "REQUEST.TABLE_FEATURES", "REQUEST.PORT_DESC",
    "REQUEST.TABLE_DESC", "REQUEST.QUEUE_DESC", "REQUEST.FLOW_MONITOR",
    "REPLY.DESC", "REPLY.FLOW", "REPLY.AGGREGATE", "REPLY.TABLE",
    "REPLY.PORT_STATS", "REPLY.QUEUE", "REPLY.GROUP", "REPLY.GROUP_DESC",
    "REPLY.GROUP_FEATURES", "REPLY.METER", "REPLY.METER_CONFIG",
    "REPLY.METER_FEATURES", "REPLY.TABLE_FEATURES", "REPLY.PORT_DESC",
    "REPLY.TABLE_DESC", "REPLY.QUEUE_DESC", "REPLY.FLOW_MONITOR",
    "BARRIER_REQUEST", "BARRIER_REPLY", "QUEUE_GET_CONFIG_REQUEST",
    "QUEUE_GET_CONFIG_REPLY", "ROLE_REQUEST", "ROLE_REPLY",
    "GET_ASYNC_REQUEST", "GET_ASYNC_REPLY", "SET_ASYNC", "METER_MOD",
    "ROLE_STATUS", "TABLE_STATUS", "REQUESTFORWARD", "BUNDLE_CONTROL",
    "BUNDLE_ADD_MESSAGE"
}


def make_handler(callback, type_, subtype='', options=None):
    """Factory function to create appropriate handler.

    Supported types: message, event
    """
    if type_ == 'message':
        return MessageHandler(callback, type_, subtype, options)
    if type_ == 'event':
        return EventHandler(callback, type_, subtype, options)
    raise ValueError('make_handler: Unknown handler type: "%s"' % type_)


class BaseHandler(object):
    """A Handler is a wrapper around an event callback.

    Attributes:
        callback (function): Callback function or coroutine
        type (str): "message", "event" or "command"
        subtype (str | function): Event or message subtype
        options (Optional[dict]): Handler options.
    """

    def __init__(self, callback, type_, subtype='', options=None):
        self.callback = callback
        self.type = type_
        self.subtype = subtype.upper() if isinstance(subtype, str) else subtype
        self.options = options

    def match(self, event):
        raise NotImplementedError("Please implement this method")

    def __call__(self, event, app):
        """Invoke handler and ignore the return value."""
        datapath_id = event('datapath_id')
        conn_id = event('conn_id')
        if asyncio.iscoroutinefunction(self.callback):
            app.ensure_future(
                self.callback(event), datapath_id=datapath_id, conn_id=conn_id)
        else:
            task = asyncio.Task.current_task()
            if task:
                task.ofp_task_locals = {
                    'datapath_id': datapath_id,
                    'conn_id': conn_id
                }
            self.callback(event)

    def __repr__(self):
        cb_name = self.callback.__name__ if self.callback else 'NONE'
        return '%s[%s] %s %r' % (self.type, self.subtype, cb_name,
                                 self.options)

    def verify(self):
        return _verify_callback(self.callback, 1)

    def help(self):
        """Return help text."""
        text = self.callback.__doc__
        if not text:
            return 'No help available'
        return inspect.cleandoc(text)

    def help_brief(self):
        """Return summary line from help text."""
        text = self.callback.__doc__
        if not text:
            return 'No help available'
        return text.strip().split('\n', 1)[0]


class MessageHandler(BaseHandler):
    def match(self, event):
        # Check subtype to see if we can return False immediately.
        if callable(self.subtype):
            if not self.subtype(event.type):
                return False
        elif self.subtype != event.type:
            return False
        # Check for events that don't have a datapath_id. For these, the app
        # must explicitly opt in using `datapath_id=None`.
        if 'datapath_id' not in event:
            if self.options.get('datapath_id', '') is not None:
                return False
        else:
            if self.options.get('datapath_id', '') is None:
                return False
        # Check for matching option values in event.
        for key, value in self.options.items():
            if not _match_message(key, value, event):
                return False
        return True

    def verify(self):
        if not _verify_callback(self.callback, 1):
            return False
        if callable(self.subtype):
            if not _verify_callback(self.subtype, 1):
                LOGGER.warning('Message handler invalid subtype: %r',
                               self.subtype)
                return False
        elif self.subtype not in _MSG_SUBTYPES:
            LOGGER.warning(
                'Message handler subtype not recognized: %s',
                self.subtype,
                stack_info=True)
        return True


class EventHandler(BaseHandler):
    def match(self, event):
        # Check subtype to see if we can return false immediately.
        if callable(self.subtype):
            if not self.subtype(event['event']):
                return False
        elif event['event'] != self.subtype:
            return False
        # Check for matching option values in event.
        for key, value in self.options.items():
            if not _match_event(key, value, event):
                return False
        return True

    def verify(self):
        if not _verify_callback(self.callback, 1):
            return False
        if callable(self.subtype):
            if not _verify_callback(self.subtype, 1):
                LOGGER.warning('Event handler invalid subtype: %r',
                               self.subtype)
                return False
        return True


def _verify_callback(callback, param_count):
    """Make sure callback  has the expected number of positional parameters."""
    if not callable(callback):
        LOGGER.error('Callback is not a callable function: %s', callback)
        return False
    sig = inspect.signature(callback)
    if len(sig.parameters) != param_count:
        LOGGER.error('Callback has unexpected number of parameters: %s',
                     callback)
        return False
    return True


def _match_message(key, value, event):
    """Return true if `key` and `value` exist within the given message."""
    if key == 'datapath_id' and value is None:
        return True
    val = str(value).upper()
    if key in event.msg:
        return str(event.msg[key]).upper() == val
    if 'pkt' in event.msg:
        pkt = event.msg.pkt
        if key in pkt:
            return str(pkt[key]).upper() == val
    return False


def _match_event(key, value, event):
    """Return true if `key` and `value` exist within the given event."""
    val = str(value).upper()
    if key in event:
        return str(event[key]).upper() == val
    return False
