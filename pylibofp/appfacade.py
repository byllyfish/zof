import argparse
import asyncio
from .exception import CommandException


class AppFacade(object):
    """Facade that provides access to API functions.

    This object will be returned by `ofp_app` function.

    Example:

        from ofp_app import ofp_app, ofp_run

        app = ofp_app('appname')

        @app.message(any)
        def any_message(event):
            print(event)

        if __name__ == '__main__':
            ofp_run()

    Args:
        app (ControllerApp): Internal app object.

    Attributes:
        name (str): App name.
        logger (Logger): App's logger.
    """

    def __init__(self, app):
        self._app = app
        self.name = app.name
        self.logger = app.logger
        #self.controller = app.parent

        self.ensure_future = app.ensure_future
        self.subscribe = app.subscribe
        self.unsubscribe = app.subscribe
        self.post_event = app.post_event
        self.rpc_call = app.rpc_call

    # Decorators

    def message(self, subtype, **kwds):
        """Message decorator.
        """

        def _wrap(func):
            return self.subscribe(func, 'message', subtype, kwds)

        return _wrap

    def event(self, subtype, **kwds):
        """Event decorator.
        """

        def _wrap(func):
            return self.subscribe(func, 'event', subtype, kwds)

        return _wrap

    def command(self, subtype, **kwds):
        """Command decorator.
        """

        def _wrap(func):
            return self.subscribe(func, 'command', subtype, kwds)

        return _wrap

    # TODO(bfish): Add an 'intercept' decorator for intercepting outgoing
    # messages. (Advanced)

    # Basic Functions

    #def compile(self, msg):
    #    """Compile an OpenFlow message template.
    #    """
    #    return CompiledMessage(self._app.parent, msg)

    # RPC Functions

    async def connect(self, endpoint, *, options=(), versions=()):
        """Make an outgoing OpenFlow connection.
        """
        result = await self.rpc_call(
            'OFP.CONNECT',
            endpoint=endpoint,
            options=options,
            versions=versions)
        return result.conn_id

    def all_apps(self):
        return list(self._app.parent.apps)

    #def post_event(self, event, **kwds):
    #    self._app.post_event(make_event(event=event.upper(), **kwds))


class _ArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if asyncio.Task.current_task():
            raise CommandException(status=0)
        super().exit(status, message)


AppFacade.command.ArgumentParser = _ArgumentParser
