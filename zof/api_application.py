import os
from .controller import Controller
from .controllerapp import ControllerApp
from .logging import init_logging

# Enable logging before the first Application is created.
_DEBUG = os.environ.get('zof_DEBUG')
if _DEBUG:
    init_logging('info' if _DEBUG.lower() == 'info' else 'debug')


class Application(object):
    """The Application class represents a controller "app". Your app's
    code registers for events and issues commands primarily via an
    `Application` instance.

    Example:

        import zof

        app = zof.Application('appname')

        @app.message(any)
        def any_message(event):
            print(event)

        if __name__ == '__main__':
            zof.run()

    Args:
        name (str): Name of the app.
        precedence (int): Precedence for app event dispatch.
        exception_fatal (bool|str): If true, abort app when a handler raises
          an exception. When the value is a string, it's treated as the name of
          the exception logger `zof.<exc_log>`.
        arg_parser (argparse.ArgumentParser): App's argument parser.

    Attributes:
        name (str): App name.
        logger (Logger): App's logger.
    """

    def __init__(self,
                 name,
                 *,
                 exception_fatal=False,
                 precedence=100,
                 arg_parser=None,
                 has_datapath_id=True):
        controller = Controller.singleton()
        if controller.find_app(name):
            raise ValueError('App named "%s" already exists.' % name)

        # Construct internal ControllerApp object.
        app = ControllerApp(
            controller,
            name=name,
            ref=self,
            exception_fatal=exception_fatal,
            precedence=precedence,
            arg_parser=arg_parser,
            has_datapath_id=has_datapath_id)

        self._app = app
        self.name = app.name
        self.logger = app.logger
        self.ensure_future = app.ensure_future
        self.post_event = app.post_event
        self.rpc_call = app.rpc_call

    @property
    def args(self):
        return self._app.controller.args

    @property
    def precedence(self):
        return self._app.precedence

    @property
    def phase(self):
        return self._app.controller.phase

    @property
    def apps(self):
        return [app.ref for app in self._app.controller.apps]

    @property
    def oftr_connection(self):
        return self._app.controller.conn

    @property
    def handlers(self):
        # TODO(bfish): Implement later...
        #return list(self._app.handlers)
        raise NotImplementedError('Not implemeted yet')

    # Decorators

    def message(self, subtype, **kwds):
        """Message decorator.
        """

        def _wrap(func):
            return self._app.register(func, 'message', subtype, kwds)

        return _wrap

    def event(self, subtype, **kwds):
        """Event decorator.
        """

        def _wrap(func):
            return self._app.register(func, 'event', subtype, kwds)

        return _wrap

    # RPC Functions

    async def connect(self, endpoint, *, options=(), versions=(), tls_id=0):
        """Make an outgoing OpenFlow connection.
        """
        result = await self.rpc_call(
            'OFP.CONNECT',
            endpoint=endpoint,
            tls_id=tls_id,
            options=options,
            versions=versions)
        return result.conn_id

    async def close(self, *, conn_id=0, datapath_id=None):
        """Close an OpenFlow connection."""
        result = await self.rpc_call(
            'OFP.CLOSE', conn_id=conn_id, datapath_id=datapath_id)
        return result.count
