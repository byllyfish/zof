.. _dispatch:

Event Dispatch
==============

Events are dispatched to apps in order of precedence.

All apps are initially sorted by precedence value in ascending order. The default precedence value for an app is 100. You have the option to set the precedence value when you call ofp_app(). Where two apps have the same precedence value, they remain in their original order.

Events are dispatched one at a time to each app in order. Each app checks its handlers from top to bottom, and runs the first handler that matches. Then, the dispatcher proceeds to the next app.

After the event is dispatched to all apps, the dispatcher yields any running async tasks before processing the next event.


Event
-----

There are two types of events: message events and internal events. Message events have a 'type' attribute. They represent incoming OpenFlow messages.

::

    {
      'type': 'PACKET_IN',
      'msg': {
          ...
      }
    }

Internal events have an 'event' attribute instead of a 'type' attribute. Internal events are used by the framework for communication between apps.

::

    {
      'event': 'SIGNAL',
      'signal': 'SIGHUP',
      'exit': True
    }

Event attributes can be accessed using dot notation "event.type" or as keys "event['type']".

Handler
-------

A handler is a function with a `@app.message` or `@app.event` decorator. The function must take exactly one `event` argument.

The decorator describes the handler's trigger condition. @app.message(type, ...) specifies an OpenFlow message type.  @app.event(event, ...) specifies an internal event type. 


Handler Functions
-----------------

A handler function may be synchronous or asynchronous. If a handler is synchronous, the entire handler executes before proceeding to the next app. If the handler is asynchronous, a new async task is created and the *first step* of the async task executes before proceeding to the next app.

::

    # Synchronous handler
    @app.message('packet_in')
    def packet_in(event):
        ...

    # Asynchronous handler (uses async def)
    @app.message('features_reply')
    async def features_reply(event):
        ...


Handler functions must not block or perform cpu-intensive operations.


Message Handlers and Implicit Variables
---------------------------------------



Async Tasks and Scope
---------------------

Use the app.ensure_future() method to start a new asynchronous task. This task is scheduled independently and managed by the framework.



Blocking or CPU-Intensive Tasks
-------------------------------

::

    @app.event('start')
    async def start(event):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, functools.partial(blocking_operation, 1, foo=2))


    def blocking_operation(n, *, foo):
        # Runs in separate thread. Be careful with shared mutable state!
        os.sleep(10)



Stopping Propagation
--------------------

An app handler can stop propagation of an event by raising a `StopPropagationException`. The handler must be synchronous; calling StopPropagationException from an asynchronous handler will not work.


Events are Mutable
------------------

Events are mutable. An app's handler may modify an event before it reaches later apps. This feature must be used with care, since handlers won't make copies of the event object. See `Signal Handling` for one way event mutability is used.
