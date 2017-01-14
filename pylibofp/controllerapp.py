"""Implements ControllerApp class."""

import logging
from collections import defaultdict
from pylibofp.handler import make_handler
import pylibofp.exception as _exc
from .event import Event


class ControllerApp(object):
    """Concrete class representing a controller application.

    Attributes:
        id (int): App ID.
        name (str): App name.
        precedence (int): App precedence.
        ofversion (...): Supported OpenFlow versions.
        parent (Controller): App's parent controller object.
        logger (Logger): App's logger.
        handlers (Dict[str,BaseHandler]): App handlers.
        counters (Dict[str,int]): App stat counters.
    Args:
        parent (Controller): Parent controller object.
        name (str): App name.
        ofversion (Optional[str]): Supports OpenFlow versions.
    """
    _curr_app_id = 0

    def __init__(self, parent, *, name, ofversion=None):
        self.id = ControllerApp.next_app_id()
        self.name = name
        self.precedence = 100
        self.ofversion = ofversion
        self.handlers = {}
        self.counters = defaultdict(lambda: 0)

        # Add app to parent's list of app's.
        parent.apps.append(self)
        self.parent = parent  # TODO: need weakref?

        self.logger = logging.getLogger('pylibofp.%s' % self.name)
        self.logger.info('Create app "%s"', self.name)

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
            for handler in self.handlers.get(handler_type, []):
                if handler.match(event):
                    try:
                        handler(event, self)
                        break
                    except _exc.FallThroughException:
                        self.logger.debug('_handle: FallThroughException')
        except Exception:  # pylint: disable=broad-except
            self.logger.exception(
                'Exception caught while handling "%s" event: %s', handler_type,
                event)

    def post_event(self, event):
        """
        Function used to send an internal event to all app modules.
        """
        assert isinstance(event, Event)
        self.logger.debug('post_event %s', event)
        self.counters['post_event'] += 1
        self.parent._post_event(event)

    def rpc_call(self, method, **params):
        """
        Function used to send a RPC request and receive a response.
        """
        self.logger.debug('rpc_call %s', method)
        self.counters['rpc_call'] += 1
        return self.parent._rpc_call(method, **params)

    def ensure_future(self, coroutine, *, datapath_id=None, conn_id=None):
        """
        Function used by an app to run an async coroutine, under a specific
        scope.
        """
        scope_key = datapath_id if datapath_id else conn_id
        task_locals = dict(datapath_id=datapath_id, conn_id=conn_id)
        return self.parent._ensure_future(
            coroutine, scope_key=scope_key, app=self, task_locals=task_locals)

    def subscribe(self, callback, type_, subtype, options):
        """
        Function used to subscribe a handler.
        """
        handler = make_handler(callback, type_, subtype, options)
        if not handler.verify():
            self.logger.error('Failed to subscribe %s', handler)
            return None
        hs = self.handlers.setdefault(handler.type, [])
        hs.append(handler)
        self.logger.debug('Subscribe %s', handler)
        return handler

    def unsubscribe(self, callback):
        """
        Function used to unsubscribe a handler.
        """
        for key in self.handlers:
            for handler in self.handlers[key]:
                if handler.callback is callback:
                    self.logger.debug('Unsubscribe %s', handler)
                    self.handlers[key].remove(handler)
                    return

    @staticmethod
    def next_app_id():
        ControllerApp._curr_app_id += 1
        return ControllerApp._curr_app_id
