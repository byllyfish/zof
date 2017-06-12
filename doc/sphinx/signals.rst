Signal Handling
===============

An app handles signals by listening for a SIGNAL event.

::
    @app.event('signal', signal='SIGHUP')
    def sighup(event):
        event.exit = False
        ...

The framework automatically listens for SIGTERM, SIGINT, and SIGHUP signals. By default, these signals cause
the program to shutdown cleanly. To prevent the signal from quitting the program, your
handler can change `event.exit` to False.

You can also listen for other signals. By default, these signals do not quit the program unless you set `event.exit` to True. To listen for a signal, specify the signal name using the `signal` attribute.

::
    @app.event('signal', signal='SIGUSR1')
    def siguser1(event):
        ...
