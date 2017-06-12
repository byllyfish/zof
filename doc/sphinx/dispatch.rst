Event Dispatch
==============

The event dispatch loop is single-threaded. Events are dispatched to apps in a deterministic way.

All apps are initially sorted by precedence value in ascending order. Where two apps have the same precedence value, their order is determined by app name. The default precedence value for an app is 100. You have the option to set the precedence value when you call ofp_app().

Events are dispatched one at a time to each app in order. Each app checks its handlers from top to bottom, and runs the first handler that matches. Then, the dispatcher proceeds to the next app.

Events are mutable. An app's handler may modify an event before it reaches later apps.

A handler may be synchronous or asynchronous. If a handler is synchronous, the entire handler executes before proceeding to the next app. If the handler is asynchronous, a new async task is created and the *first step* of the async task executes before proceeding to the next app.

After the event is dispatched to all apps, the dispatcher yields again to any running async tasks.


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
        result = await blocking_operation(10, foo=5)


    @app.executor()
    def blocking_operation(n, *, foo):
        ...



Stopping Propagation
--------------------

An app handler can stop propagation of an event by raising a `StopPropagationException`. The handler must be synchronous.

