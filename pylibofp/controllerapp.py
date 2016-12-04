"""Implements ControllerApp class."""

import logging
import textwrap
import string
import json
import collections
from pylibofp.handler import make_handler
import pylibofp.exception as _exc


class ControllerApp(object):
    """Concrete class representing a controller application.

    Attributes:
        name (str): App name.
        ofversion (...): Supported OpenFlow versions
        parent (Controller): App's parent controller object.
        logger (Logger): App's logger.

    Args:
        parent (Controller): Parent controller object.
        name (str): App name.
        ofversion (Optional[str]): Supports OpenFlow versions.
    """

    def __init__(self, parent, *, name, ofversion=None):
        self.name = name
        self.ofversion = ofversion
        self._handlers = {}

        # Add app to parent's list of app's.
        parent.apps.append(self)
        self.parent = parent  # TODO: need weakref?

        self.logger = logging.getLogger('pylibofp.%s' % self.name)
        self.logger.info('Create app "%s"', self.name)

    def channel(self, event):
        """
        Invoked by Controller when an 'OFP.CHANNEL' notification is received.
        """
        self._handle(event, 'channel')

    def message(self, event):
        """
        Invoked by Controller when an 'OFP.MESSAGE' notification is received.
        """
        self._handle(event, 'message')

    def event(self, event):
        """
        Invoked by Controller when an event is received.
        """
        self._handle(event, 'event')

    def _handle(self, event, handler_type):
        """
        Helper function to handle events.
        """
        try:
            for handler in self._handlers.get(handler_type, []):
                if handler.match(event):
                    try:
                        handler(event)
                        break
                    except _exc.FallThroughException:
                        self.logger.debug('_handle: FallThroughException')
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                'Exception caught while handling "%s" event: %s', handler_type,
                event)

    def send(self, msg, **kwds):
        """
        Function used to send an OpenFlow message (fire and forget).
        """
        xid = kwds.get('xid', self.parent._next_xid())
        event = _translate_msg_to_event(msg, kwds, xid)
        self.logger.debug('send {\n%s\n}', event)
        self.parent._write(event)

    def request(self, msg, **kwds):
        """
        Function used to send an OpenFlow request and receive a response.
        """
        xid = kwds.get('xid', self.parent._next_xid())
        event = _translate_msg_to_event(msg, kwds, xid)
        self.logger.debug('request {\n%s\n}', event)
        return self.parent._write(event, xid)

    def post_event(self, **event):
        """
        Function used to send an internal event to all app modules.
        """
        assert isinstance(event, dict) and 'event' in event
        self.logger.debug('post_event %s', event)
        self.parent._post_event(event)

    def rpc_call(self, method, **params):
        """
        Function used to send a RPC request and receive a response.
        """
        self.logger.debug('rpc_call %s', method)
        return self.parent._rpc_call(method, **params)

    def ensure_future(self, coroutine, *, datapath_id=None, conn_id=None):
        """
        Function used by an app to run an async coroutine, under a specific
        scope.
        """
        scope_key = datapath_id if datapath_id else conn_id
        return self.parent._ensure_future(
            coroutine, scope_key=scope_key, logger=self.logger)

    def subscribe(self, callback, type_, subtype, options):
        """
        Function used to subscribe a handler.
        """
        handler = make_handler(callback, type_, subtype, options)
        if not handler.verify():
            self.logger.error('Failed to subscribe %s', handler)
            return None
        hs = self._handlers.setdefault(handler.type, [])
        hs.append(handler)
        self.logger.debug('Subscribe %s', handler)
        return handler

    def unsubscribe(self, callback):
        """
        Function used to unsubscribe a handler.
        """
        for key in self._handlers:
            for handler in self._handlers[key]:
                if handler.callback is callback:
                    self.logger.debug('Unsubscribe %s', handler)
                    self._handlers[key].remove(handler)
                    return

    def __repr__(self):
        """
        Return human-readable description of app's configuration.
        """
        text = ['%s:' % self._name]
        for handlers in self._handlers.values():
            for h in handlers:
                text.append('  ' + repr(h))
        return '\n'.join(text)


def _translate_msg_to_event(msg, kwds, xid):
    """
    Helper function to translate an OpenFlow message in string or object format
    to a valid `OFP.SEND` event.

    `msg` may be a YAML string or an object.
    """
    if isinstance(msg, str):
        msg = _translate_msg_str(msg, kwds)
        hdr = ''
        if 'datapath_id' in kwds:
            hdr += 'datapath_id: %s\n' % kwds['datapath_id']
        if xid is not None:
            hdr += 'xid: %d\n' % xid
        msg = hdr + msg
        return 'method: OFP.SEND\nparams:\n  %s' % msg.replace('\n', '\n  ')
    else:
        if 'datapath_id' in kwds:
            msg['datapath_id'] = kwds['datapath_id']
        if xid is not None:
            msg['xid'] = xid
        return dict(method='OFP.SEND', params=msg)


def _translate_msg_str(msg, kwds):
    # Translate `bytes` values to hexadecimal and escape all string values.
    for key in kwds:
        val = kwds[key]
        if isinstance(val, bytes):
            kwds[key] = val.hex()
        elif isinstance(val, str):
            kwds[key] = json.dumps(val)
    return string.Template(textwrap.dedent(msg).strip()).substitute(kwds)


_OFP = collections.namedtuple(
    '_OFP',
    'message channel event send request post_event configure rpc_call ensure_future shared config datapaths logger subscribe unsubscribe'
)


def _make_ofp(app):
    return _OFP(app.message_decorator, app.channel_decorator,
                app.event_decorator, app.send, app.request, app.post_event,
                app.configure, app.rpc_call, app.ensure_future,
                app.parent.shared, app.parent.config, app.parent.datapaths,
                app.logger, app.subscribe, app.unsubscribe)
