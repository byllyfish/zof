"""Implements ControllerApp class."""

import logging
import inspect
import os
import signal
from .handler import make_handler
from .event import make_event
from . import exception as _exc


class ControllerApp(object):
    """Concrete class representing a controller application.

    Attributes:
        name (str): App name.
        precedence (int): App precedence.
        ofversion (...): Supported OpenFlow versions.
        kill_on_exception (bool): Terminate immediately if app raises exception.
        parent (Controller): App's parent controller object.
        logger (Logger): App's logger.
        handlers (Dict[str,BaseHandler]): App handlers.
    Args:
        parent (Controller): Parent controller object.
        name (str): App name.
        ofversion (Optional[str]): Supports OpenFlow versions.
        kill_on_exception (bool): Terminate immediately if app raises exception.
    """
    _curr_app_id = 0

    def __init__(self,
                 parent,
                 *,
                 name,
                 ofversion=None,
                 kill_on_exception=False):
        self.name = name
        self.precedence = 100
        self.ofversion = ofversion
        self.handlers = {}
        self.kill_on_exception = kill_on_exception

        # Add this app to parent's list of app's.
        parent.apps.append(self)
        self.parent = parent  # TODO: need weakref?

        self.logger = logging.getLogger('pylibofp.%s' % self.name)
        self.logger.info('Create app "%s"', self.name)

    def handle_event(self, event, handler_type):
        """Handle events.
        """
        try:
            for handler in self.handlers.get(handler_type, []):
                if handler.match(event):
                    handler(event, self)
                    break
        except _exc.StopPropagationException:
            # Pass this exception up to controller.
            raise
        except Exception:  # pylint: disable=broad-except
            self.handle_exception(event, handler_type)

    def handle_exception(self, event, handler_type):
        """Handle exception."""
        self.logger.exception('Exception caught while handling "%s": %r',
                              handler_type, event)
        if self.kill_on_exception:
            self.logger.critical(
                'Terminate controller; kill_on_exception set for app "%s"',
                self.name)
            logging.shutdown()
            os.kill(os.getpid(), signal.SIGKILL)

    def post_event(self, event, **kwds):
        """Function used to send an internal event to all app modules.
        """
        self.logger.debug('post_event %s', event)
        self.parent.post_event(make_event(event=event.upper(), **kwds))

    def rpc_call(self, method, **params):
        """Function used to send a RPC request and receive a response.
        """
        self.logger.debug('rpc_call %s', method)
        return self.parent.rpc_call(method, **params)

    def ensure_future(self, coroutine, *, datapath_id=None, conn_id=None):
        """Function used by an app to run an async coroutine, under a specific
        scope.
        """
        assert inspect.isawaitable(coroutine)
        scope_key = datapath_id if datapath_id else conn_id
        task_locals = dict(datapath_id=datapath_id, conn_id=conn_id)
        return self.parent.ensure_future(
            coroutine, scope_key=scope_key, app=self, task_locals=task_locals)

    def subscribe(self, callback, type_, subtype, options):
        """Function used to subscribe a handler.
        """
        handler = make_handler(callback, type_, subtype, options)
        if not handler.verify():
            self.logger.error('Failed to subscribe %s', handler)
            return None
        handlers = self.handlers.setdefault(handler.type, [])
        handlers.append(handler)
        self.logger.debug('Subscribe %s', handler)
        return handler

    def unsubscribe(self, callback):
        """Function used to unsubscribe a handler.
        """
        for key in self.handlers:
            for handler in self.handlers[key]:
                if handler.callback is callback:
                    self.logger.debug('Unsubscribe %s', handler)
                    self.handlers[key].remove(handler)
                    return
