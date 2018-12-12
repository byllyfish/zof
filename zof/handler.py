import logging
import asyncio
from zof.callbackinfo import CallbackInfo

LOGGER = logging.getLogger(__package__)

_MSG_SUBTYPES = {
    "CHANNEL_UP", "CHANNEL_DOWN", "CHANNEL_ALERT", "HELLO", "ERROR",
    "ECHO_REQUEST", "ECHO_REPLY", "EXPERIMENTER", "FEATURES_REQUEST",
    "FEATURES_REPLY", "GET_CONFIG_REQUEST", "GET_CONFIG_REPLY", "SET_CONFIG",
    "PACKET_IN", "FLOW_REMOVED", "PORT_STATUS", "PACKET_OUT", "FLOW_MOD",
    "GROUP_MOD", "PORT_MOD", "TABLE_MOD", "DESC_REQUEST", "FLOW_DESC_REQUEST",
    "AGGREGATE_STATS_REQUEST", "TABLE_STATS_REQUEST", "PORT_STATS_REQUEST",
    "QUEUE_STATS_REQUEST", "GROUP_STATS_REQUEST", "GROUP_DESC_REQUEST",
    "GROUP_FEATURES_REQUEST", "METER_STATS_REQUEST", "METER_CONFIG_REQUEST",
    "METER_FEATURES_REQUEST", "TABLE_FEATURES_REQUEST", "PORT_DESC_REQUEST",
    "TABLE_DESC_REQUEST", "QUEUE_DESC_REQUEST", "FLOW_MONITOR_REQUEST",
    "DESC_REPLY", "FLOW_DESC_REPLY", "AGGREGATE_STATS_REPLY", "TABLE_STATS_REPLY",
    "PORT_STATS_REPLY", "QUEUE_STATS_REPLY", "GROUP_STATS_REPLY", "GROUP_DESC_REPLY",
    "GROUP_FEATURES_REPLY", "METER_STATS_REPLY", "METER_CONFIG_REPLY",
    "METER_FEATURES_REPLY", "TABLE_FEATURES_REPLY", "PORT_DESC_REPLY",
    "TABLE_DESC_REPLY", "QUEUE_DESC_REPLY", "FLOW_MONITOR_REPLY",
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
        self.callback = None
        self.callback_info = CallbackInfo(callback)
        self.type = type_
        self.subtype = subtype.upper() if isinstance(subtype, str) else subtype
        self.options = options

    def bind(self, instance=None):
        """Bind handler to instance (or None if there's no instance)."""
        assert self.callback_info.args_required == 1
        self.callback = self.callback_info.bind(instance)

    def match(self, event):
        raise NotImplementedError("Please implement this method")

    def __call__(self, event, app):
        """Invoke handler and ignore the return value."""
        datapath_id = event.get('datapath_id')
        conn_id = event.get('conn_id')
        if asyncio.iscoroutinefunction(self.callback):
            app.ensure_future(
                self.callback(event), datapath_id=datapath_id, conn_id=conn_id)
        else:
            task = asyncio.Task.current_task()
            if task:
                task.zof_task_app = app
                task.zof_task_locals = {
                    'datapath_id': datapath_id,
                    'conn_id': conn_id
                }
            self.callback(event)

    def __repr__(self):
        cb_name = self.callback_info.name
        return '%s[%s] %s %r' % (self.type, self.subtype, cb_name,
                                 self.options)


class MessageHandler(BaseHandler):
    def match(self, event):
        # Check subtype to see if we can return False immediately.
        event_type = event['type']
        if callable(self.subtype):
            if not self.subtype(event_type):
                return False
        elif self.subtype != event_type:
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


def _match_message(key, value, event):
    """Return true if `key` and `value` exist within the given message."""
    if key == 'datapath_id' and value is None:
        return True
    val = str(value).upper()
    msg = event['msg']
    if key in msg:
        return str(msg[key]).upper() == val
    pkt = msg.get('pkt')
    if pkt is not None and key in pkt:
        return str(pkt[key]).upper() == val
    return False


def _match_event(key, value, event):
    """Return true if `key` and `value` exist within the given event."""
    val = str(value).upper()
    if key in event:
        return str(event[key]).upper() == val
    return False
