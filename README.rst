===
zof
===


.. image:: https://img.shields.io/pypi/v/zof.svg
        :target: https://pypi.python.org/pypi/zof

.. image:: https://img.shields.io/travis/byllyfish/zof.svg
        :target: https://travis-ci.org/byllyfish/zof

.. image:: https://readthedocs.org/projects/zof/badge/?version=latest
        :target: https://zof.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status


zof is an easy-to-use library for developing OpenFlow controllers using Python/asyncio.



	import asyncio
	import zof

	class MyController(zof.Controller):
		def on_channel_up(self, dp, ofmsg):
			...

		def on_packet_in(self, dp, ofmsg):
			...

	asyncio.run(MyController().run())

In zof, OpenFlow messages are Python dictionaries using a JSON-based DSL from the oftr program. All
OpenFlow messages have the basic form::
	
	{ 
		type:    <TYPE>
	    time:    <TIME>
	    version: <VERSION>
		msg: {
			<MESSAGE>
		}
	}

For example, here is what a OFPT_PACKET_IN message will look like:


Key Features
------------

* JSON-based DSL supports: 
  * OpenFlow versions 1.0 - 1.5.
  * Packet parsing/generation for ARP, LLDP, IPv4, IPv6, UDP, TCP, ICMPv4, ICMPv6.


Install
-------

Use pip to install zof:

.. code-block:: console

  $ pip install zof

zof uses the `oftr` command line tool to translate between JSON and OpenFlow messages.

* Free software: MIT License
* Documentation: https://zof.readthedocs.io.


Features
--------

* TODO

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
