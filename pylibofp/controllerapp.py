import os
import logging
import textwrap
import string
import json
import runpy
import collections
from pylibofp.handler import make_handler
import pylibofp.exception as _exc


class ControllerApp(object):
    """
    Concrete class representing a controller application loaded from a
    python module.
    """

    def __init__(self, parent, filename):
        """
        Initialize app using path to a python module.
        """
        self._name = os.path.basename(filename)
        self._parent = parent
        self._filename = filename
        self._handlers = {}
        self.logger = logging.getLogger('pylibofp.app.%s' % self._name)

        # Load module and add decorated handlers.
        self.logger.info('Load "%s"', self._filename)
        runpy.run_path(filename, init_globals={'OFP': _make_ofp(self)})

    @property
    def parent(self):
        """
        Parent controller.
        """
        return self._parent

    @property
    def config(self):
        """
        Global config object.
        """
        return self.parent.config

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
        except Exception: # pylint: disable=broad-except
            self.logger.exception('Exception caught while handling "%s" event: %s', handler_type, event)

    def send(self, msg, **kwds):
        """
        Function used to send an OpenFlow message (fire and forget).
        """
        xid = kwds.get('xid', self._parent._next_xid())
        event = _translate_msg_to_event(msg, kwds, xid)
        self.logger.debug('send {\n%s\n}', event)
        self._parent._write(event)

    def request(self, msg, **kwds):
        """
        Function used to send an OpenFlow request and receive a response.
        """
        xid = kwds.get('xid', self._parent._next_xid())
        event = _translate_msg_to_event(msg, kwds, xid)
        self.logger.debug('request {\n%s\n}', event)
        return self._parent._write(event, xid)

    def post_event(self, **event):
        """
        Function used to send an internal event to all app modules.
        """
        assert isinstance(event, dict) and 'event' in event
        self.logger.debug('post_event %s', event)
        self._parent._post_event(event)

    def rpc_call(self, method, **params):
        """
        Function used to send a RPC request and receive a response.
        """
        self.logger.debug('rpc_call %s', method)
        return self._parent._rpc_call(method, **params)

    def configure(self, loglevel=None, ofversion=None):
        """
        Function used by an app to configure logging and OpenFlow version.
        """
        assert not loglevel or isinstance(loglevel, (str, int))
        assert not ofversion or isinstance(ofversion, list)

        if loglevel is not None:
            self.logger.setLevel(loglevel.upper())

        if ofversion is not None:
            # Check if ofversion intersects `config.ofversion`. Be aware that
            # an empty `config.ofversion` implies all versions.
            if not self.config.ofversion:
                self.config.ofversion = ofversion
            else:
                new_vers = set(self.config.ofversion) & set(ofversion)
                if not new_vers:
                    raise ValueError('Unable to use OpenFlow version %s', ofversion)
                self.config.ofversion = list(new_vers)

    def ensure_future(self, coroutine, *, datapath_id=None, conn_id=None):
        """
        Function used by an app to run an async coroutine, under a specific
        scope.
        """
        scope_key = datapath_id if datapath_id else conn_id
        return self._parent._ensure_future(coroutine, scope_key=scope_key, logger=self.logger)

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

    def message_decorator(self, subtype, **kwds):
        """
        Message subscribe decorator.
        """
        def wrap(func):
            self.subscribe(func, 'message', subtype, kwds)
        return wrap

    def channel_decorator(self, subtype, **kwds):
        """
        Channel subscribe decorator.
        """
        def wrap(func):
            self.subscribe(func, 'channel', subtype, kwds)
        return wrap

    def event_decorator(self, subtype, **kwds):
        """
        Event subscribe decorator.
        """
        def wrap(func):
            self.subscribe(func, 'event', subtype, kwds)
        return wrap

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
    'message channel event send request post_event configure rpc_call ensure_future shared config datapaths logger subscribe unsubscribe')


def _make_ofp(app):
    return _OFP(app.message_decorator, 
                app.channel_decorator, 
                app.event_decorator, 
                app.send, 
                app.request,
                app.post_event, 
                app.configure, 
                app.rpc_call, 
                app.ensure_future, 
                app.parent.shared,
                app.parent.config, 
                app.parent.datapaths,
                app.logger,
                app.subscribe,
                app.unsubscribe)

