Hello, World
============

When working with something new, it's best to start simple. This chapter 
demonstrates the basic structure of a zof controller app using a series
of "Hello, World" examples.


Hello, World
------------

Let's get started with zof by creating a "Hello, World" app that runs, but
doesn't do anything interesting.

To get started, create a new text file and enter the following program.

.. code-block:: python

    import asyncio
    import zof

    class HelloWorld(zof.Controller):

        def on_channel_up(self, dp, event):
            print(event)

        def on_channel_down(self, dp, event):
            print(event)

    controller = HelloWorld()
    asyncio.run(controller.run())

In this program, you create a subclass of `zof.Controller` named `HelloWorld`, create
a new instance of it, and then invoke the instance's `run()` async method in an event loop.

Save this in a file named `hello.py` and run it.

.. code-block:: console

    $ python hello.py

The terminal will just sit there quietly while your new program is now listeningnon TCP port 6653. You
can configure an OpenFlow switch to connect to your computer on port 6653. When it connects
or disconnects, you will see the CHANNEL_UP and CHANNEL_DOWN events output on your 
terminal. If nothing is configured to connect to your computer on port 6653, this 
program will never print anything. To stop the program, type control-C.

The `on_channel_up` method is called when an OpenFlow switch connects and
successfully negotiates a connection (CHANNEL_UP). The `on_channel_down` method is called
when an OpenFlow switch disconnects (CHANNEL_DOWN). Under the hood, zof automatically
negotiates the underlying HELLO, FEATURES_REQUEST and PORT_DESC_REQUEST OpenFlow messages
for you and combines this information into the CHANNEL_UP event.

All event handler methods begin with **on_** and contain the event name. Event handling
methods take `dp` and `event` arguments. The `dp` argument is an object that represents the
OpenFlow switch (dp is short for datapath). Your handler can use the `dp` argument to send OpenFlow
messages back to the switch. The `event` argument is a python dictionary that
contains the event details.

Events all have the same top-level structure. There is a `type` that determines the kind of event
and a `msg` whose contents varies by the event type. Here is an example of what a CHANNEL_UP
event for a 2-port switch.

.. code-block:: python

    TODO

.. note:: You can enable debug logging using the ZOFDEBUG environment variable.

    $ ZOFDEBUG=1 python hello.py

    Try running the same program in debug mode to see the output.


Lifecycle Events (Start, Stop, Exception)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Your controller class can also respond to lifecycle events. These are called when zof 
starts and stops running, or if an exception is raised in an event handler.

Let's add these to the HelloWorld class.

.. code-block:: python

    class HelloWorld(zof.Controller):

        def on_start(self):
            listen_endpoints = self.get_config().listen_endpoints
            print('Start listening on %r' % listen_endpoints)

        def on_stop(self):
            print('Stopping')

        def on_exception(self, exc):
            print('Exception raised in handler: %r' % exc)

        def on_channel_up(self, dp, event):
            print(event)

        def on_channel_down(self, dp, event):
            print(event)


Run this program as `python hello.py` and now you will see output even when no 
switches connect. Stop the program by typing control-C and you should see it
output 'Stopping'.

The lifecycle events are `on_start`, `on_stop`, and `on_exception`. Note that `on_start`
and `on_stop` don't take any arguments. In the on_start method, we are using the `get_config`
method to retrieve the zof configuration object. It contains the settings that specify how 
zof runs, such as the list of TCP ports to listen on (listen_endpoints).

on_exception is called when one of your event handlers surfaces an uncaught exception.
You might choose to log the exception or terminate the program outright. The on_exception
method takes the exception `exc` as its argument.

Configuration
~~~~~~~~~~~~~

There is a configuration object that specifies how zof runs. You can create your own 
configuration object to override the defaults. You pass the configuration object to 
your controller instance when you create it. This will be the same object returned
by the controller's get_config() method.

.. code-block: python

    config = zof.Configuration(
        listen_endpoints=['127.0.0.1:6654', '127.0.0.1:6653'],
        listen_versions=[4])

    controller = HelloWorld(config)
    zof.run(controller.run())

For more information about the available settings, see the `zof.Configuration` reference.


Async Event Handlers
~~~~~~~~~~~~~~~~~~~~

The event handlers we've shown so far are all synchronous. When an event occurs, it is 
dispatched to the corresponding event handler, and the event handler runs until it is 
finished. Then, the next event is dispatched and so on.

An async handler runs in its own task, and continues to run while other events are dispatched.

Here is an example where the `on_channel_up` handler is an async method.

.. code-block:: python

    class HelloWorld(zof.Controller):

        async def on_channel_up(self, dp, event):
            print('switch %s connected' % dp.id)
            while True:
                await asyncio.sleep(3)
                print('switch %s still connected' % dp.id)

Each time an OpenFlow switch connects, zof will create a task to run the on_channel_up
coroutine for that datapath. This task will continue to run even as other events are dispatched.
The task will be automatically cancelled when the switch disconnects.

The lifecycle event handlers on_start and on_stop may be async methods. However, zof
runs them to completion when starting and stopping, so make sure they return.
The on_exception lifecycle method must not be an async method.

There is nothing that will automatically cancel an on_channel_down handler until zof
stops, so you should make sure it returns.

... note:: Task Housekeeping (create_task)

    The controller has a create_task method that can be used to create tasks that outlive
    a datapath connection. You can create tasks in your on_start handler that will live
    while the controller is running and automatically cancelled when it stops.

    Each datapath object also has a create_task method that creates a task whose life
    is tied to the duration of the switch's connection. You can use this in lieu of making
    the handler async.

    This program snippet is identical to the the version above with `async def`.

    .. code-block:: python

        def on_channel_up(self, dp, event):
            dp.create_task(self._dp_task(dp))

        def _dp_task(self, dp):
            print('switch %s connected' % dp.id)
            while True:
                await asyncio.sleep(3)
                print('switch %s still connected' % dp.id)

Controller Initialization
~~~~~~~~~~~~~~~~~~~~~~~~~~

So far, we haven't needed an '__init__' method to our controller. You might want to initialize
your own instance variables by overriding __init__.

The zof.Controller's __init__method takes a zof.Configuration object as a parameter. You need 
to include this when calling the superclass __init__.

In the examples in this chapter, we've been using print() statements to output information.
Production zof controllers should use Python's standard logging module instead. One way to
do this is to create a self.logger instance in your controller's __init__method. Here's an 
example where we pass the logger object via a custom attribute added to the configuration
object.

.. code-block:: python

    class HelloPacket(zof.Controller):
        def __init__(self, config):
            super().__init__(config)
            self.logger = config.hello_logger

        def on_packet_in(self, dp, event):
            self.logger.info('Received PacketIn %r', event)

.. note:: The __init__ method runs **before** any asyncio event loop is created. If you need to do
    any asynchronous initialization, you can do it in an async `on_start` handler. For example,
    you might need to start and stop another asyncio service. To do this, you would provide
    async on_start and on_stop methods.


Signals
~~~~~~~

By default, a zof controller process will respond to SIGINT and SIGTERM signals by shutting down 
cleanly. You can control the signals that will exit the controller using the zof.Configuration object's
`exit_signals` value. This defaults to [signal.SIGTERM, signal.SIGINT].

If you want your controller to respond to other signals, use the asyncio API to add a new signal 
handler in your on_start handler. Here is an example that adds a handler for SIGHUP.

.. code-block:: python

    class HelloSignal(zof.Controller):
        def on_start(self):
            asyncio.get_event_loop().add_signal_handler(signal.SIGHUP, self.handle_sighup)
    
        def on_stop(self):
            asyncio.get_event_loop().remove_signal_handler(signal.SIGHUP)
    
        def handle_sighup(self):
            print('SIGHUP')


Conclusion
~~~~~~~~~~

You've seen the basic scaffolding for a controller app. In the next section, we'll show how
to send OpenFlow messages in your event handlers.

