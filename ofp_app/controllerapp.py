"""Implements ControllerApp class."""

import logging
import inspect
import os
import signal
from operator import attrgetter
from .handler import make_handler
from .event import make_event, Event
from . import exception as _exc


class ControllerApp(object):
    """Concrete class representing a controller application.

    Attributes:
        name (str): App name.
        precedence (int): App precedence.
        kill_on_exception (bool|str): Terminate immediately if app raises 
            exception.
        parent (Controller): App's parent controller object.
        logger (Logger): App's logger.
        handlers (Dict[str,List[BaseHandler]]): App handlers.
    Args:
        parent (Controller): Parent controller object.
        name (str): App name.
        kill_on_exception (bool): Terminate immediately if app raises exception.
        precedence (int): App precedence.
    """
    _curr_app_id = 0

    def __init__(self,
                 parent,
                 *,
                 name,
                 kill_on_exception=False,
                 precedence=1000):
        self.name = name
        self.precedence = precedence
        self.handlers = {}
        self.kill_on_exception = kill_on_exception
        self.set_controller(parent)

        self.logger = logging.getLogger('%s.%s' % (__package__, self.name))
        self.logger.info('Create app "%s"', self.name)

    def set_controller(self, controller):
        """Set controller parent."""
        self.parent = controller
        # Insert app into controller's list sorted by precedence.
        controller.apps.append(self)
        controller.apps.sort(key=attrgetter('precedence'))

    def handle_event(self, event, handler_type):
        """Handle event."""
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
        fatal_str = 'Fatal ' if self.kill_on_exception else ''
        self.logger.critical('%sException caught while handling "%s": %r',
                             fatal_str, handler_type, event, exc_info=True)
        if self.kill_on_exception:
            # If the value of `kill_on_exception` is a string, find the logger
            # with this name and log the critical exception here also.
            if isinstance(self.kill_on_exception, str):
                logger = logging.getLogger(self.kill_on_exception)
                logger.critical('%sException caught while handling "%s": %r',
                                fatal_str, handler_type, event, exc_info=True)
            # Shutdown the program immediately.
            logging.shutdown()
            os.kill(os.getpid(), signal.SIGKILL)

    def post_event(self, event, **kwds):
        """Function used to send an internal event to all app modules.

        Args:
            event (str | Event): event type or event object
            kwds (dict): keyword arguments for make_event
        """
        if isinstance(event, str):
            event = make_event(event=event.upper(), **kwds)
        elif not isinstance(event, Event) or len(kwds) > 0:
            raise ValueError('Invalid arguments to post_event')
        self.logger.debug('post_event %r', event)
        self.parent.post_event(event)

    def rpc_call(self, method, **params):
        """Function used to send a RPC request and receive a response."""
        self.logger.debug('rpc_call %s', method)
        return self.parent.rpc_call(method, **params)

    def ensure_future(self, coroutine, *, datapath_id=None, conn_id=None):
        """Function used by an app to run an async coroutine, under a specific
        scope.
        """
        assert inspect.isawaitable(coroutine)
        task_locals = dict(datapath_id=datapath_id, conn_id=conn_id)
        return self.parent.ensure_future(
            coroutine, app=self, task_locals=task_locals)

    def subscribe(self, callback, type_, subtype, options):
        """Function used to subscribe a handler."""
        handler = make_handler(callback, type_, subtype, options)
        if not handler.verify():
            self.logger.error('Failed to subscribe %s', handler)
            return None
        handlers = self.handlers.setdefault(handler.type, [])
        handlers.append(handler)
        self.logger.debug('Subscribe %s', handler)
        return callback

    def unsubscribe(self, callback):
        """Function used to unsubscribe a handler."""
        for key in self.handlers:
            for handler in self.handlers[key]:
                if handler.callback is callback:
                    self.logger.debug('Unsubscribe %s', handler)
                    self.handlers[key].remove(handler)
                    return

    def __repr__(self):
        evt_count = len(self.handlers.get('event', []))
        msg_count = len(self.handlers.get('message', []))
        return '<ControllerApp name="%s" precedence=%d evt=%d msg=%d>' % (self.name, self.precedence, evt_count, msg_count)
