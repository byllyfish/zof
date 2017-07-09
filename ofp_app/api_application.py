from .controller import Controller
from .controllerapp import ControllerApp


class Application(object):
    """The Application class represents a controller "app". Your app's
    code registers for events and issues commands primarily via an 
    `Application` instance.

    Example:

        from ofp_app import ofp_app, ofp_run

        app = Application('appname')

        @app.message(any)
        def any_message(event):
            print(event)

        if __name__ == '__main__':
            ofp_run()

    Args:
        name (str): Name of the app.
        precedence (int): Precedence for app event dispatch.
        kill_on_exception (bool|str): If true, abort app when a handler raises
          an exception. When the value is a string, it's treated as the name of
          the exception logger `ofp_app.<exc_log>`.

    Attributes:
        name (str): App name.
        logger (Logger): App's logger.
    """

    def __init__(self, name, *, precedence=100, kill_on_exception=False):
        controller = Controller.singleton()
        if controller.find_app(name):
            raise ValueError('App named "%s" already exists.' % name)

        # Construct internal ControllerApp object.
        app = ControllerApp(controller, name=name, kill_on_exception=kill_on_exception, precedence=precedence)
        
        self._app = app
        self.name = app.name
        self.logger = app.logger
        self.ensure_future = app.ensure_future
        self.post_event = app.post_event
        self.rpc_call = app.rpc_call

    # Decorators

    def message(self, subtype, **kwds):
        """Message decorator.
        """

        def _wrap(func):
            return self._app.subscribe(func, 'message', subtype, kwds)

        return _wrap

    def event(self, subtype, **kwds):
        """Event decorator.
        """

        def _wrap(func):
            return self._app.subscribe(func, 'event', subtype, kwds)

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
        result = await self.rpc_call('OFP.CLOSE', conn_id=conn_id, datapath_id=datapath_id)
        return result.count

    def all_apps(self):
        return list(self._app.controller.apps)

    #def post_event(self, event, **kwds):
    #    self._app.post_event(make_event(event=event.upper(), **kwds))
