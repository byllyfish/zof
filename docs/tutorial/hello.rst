Hello, World
------------

Let's get started with zof by creating a "Hello, World" app that runs, but
doesn't do anything interesting.

To get started, create a new text file and enter the following program.

.. codeblock:: python

	import asyncio
	import zof


	class HelloWorld(zof.Controller):

		def on_channel_up(self, dp, event):
			print(event)

		def on_channel_down(self, dp, event):
			print(event)


	controller = HelloWorld()
	asyncio.run(controller.run())

Save this in a file named `hello.py` and run it.

The terminal will just sit there listening quietly on TCP port 6653. You
can configure an OpenFlow switch to connect to your computer. When it connects
or disconnects, you will see the events output on your terminal. If nothing
is configured to connect to your computer on port 6653, this program will never
print anything. To stop the program, type control-C.

The `on_channel_up` method is called when an OpenFlow switch connects and
successfully negotiates a connection (called a CHANNEL_UP). The `on_channel_down` method is called
when an OpenFlow switch disconnects (called a CHANNEL_DOWN).

All event handler methods begin with **on_** and contain the event name. Event handling
methods take `dp` and `event` arguments. The `dp` argument is an object that represents the
OpenFlow switch (dp is short for datapath). Your handler can use the `dp` argument to send OpenFlow
messages back to the switch. The `event` argument is a python dictionary that
contains the event details.

.. note:: You can enable debug logging using the ZOFDEBUG environment variable::

		$ ZOFDEBUG=1 python hello.py

	Try running the same program in debug mode to see the output.
