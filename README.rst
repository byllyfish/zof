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


`zof` is a library for developing OpenFlow controllers using Python3/asyncio. To 
create an OpenFlow controller, subclass `zof.Controller` and define methods to handle 
OpenFlow events.

.. code-block:: python

    import asyncio
    import zof

    class MyController(zof.Controller):
        def on_channel_up(self, dp, ofmsg):
            ...

        def on_channel_down(self, dp, ofmsg):
            ...

        def on_packet_in(self, dp, ofmsg):
            ...

    asyncio.run(MyController().run())

In `zof`, OpenFlow messages are Python dictionaries using a JSON-based DSL from the `oftr` program.

.. code-block:: yaml

    { 
      type: <TYPE>
      msg: {
        ...
      }
    }

For example, an OFPT_PACKET_IN message will look like this...





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

* JSON-based DSL
* TODO


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
