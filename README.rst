zof: OpenFlow App Framework
================================

`zof` is a Python framework for creating asyncio-based applications that control 
the network using the OpenFlow protocol. `zof` uses a separate *oftr* process to 
terminate OpenFlow connections and translate OpenFlow messages to JSON.

.. figure:: doc/sphinx/_static/img/zof_architecture.png
    :align: center
    :alt: Architecture diagram
    
    Architecture: The oftr process translates OpenFlow to JSON.

There is no built-in OpenFlow API. You construct OpenFlow messages via YAML strings or Python dictionaries. 
Incoming OpenFlow messages are generic Python objects.  Special OpenFlow constants such as 'NO_BUFFER' appear as strings.

::

    type: FLOW_MOD
    msg:
      command: ADD
      match:
        - field: IN_PORT
          value: 1
        - field: ETH_DST
          value: 00:00:00:00:00:01
      instructions:
        - instruction: APPLY_ACTIONS
          actions:
            - action: OUTPUT
              port_no: ALL

The basic building block of zof is an `app`. An `app` is associated with various message and event handlers.
You create an app object using the `zof` function. Then, you associate handlers using the app's `message` decorator.

::

    import zof

    app = zof.Application('app_name_here')

    @app.message('packet_in')
    def packet_in(event):
        app.logger.info('packet_in message %r', event)

    @app.message(any)
    def other(event):
        app.logger.info('other message %r', event)

    if __name__ == '__main__':
        zof.run()

This app handles 'PACKET_IN' messages using the packet_in function. All other messages are dispatched to the `other` function.

An OpenFlow application may be composed of multiple "app modules".  The framework includes built-in "system modules" that you can build upon.

.. (TODO) image of command line 


Requirements
------------

- Python 3.5.1 or later
- oftr command line tool


Install - Linux
---------------

::

    # Install /usr/bin/oftr dependency.
    sudo add-apt-repository ppa:byllyfish/oftr
    sudo apt-get update
    sudo apt-get install oftr

    # Create virtual environment and install latest zof.
    python3.5 -m venv myenv
    source myenv/bin/activate
    pip install git+https://github.com/byllyfish/zof.git


Demos
-----

To run the controller demo::

    python -m zof.demo.layer2 --help


.. (TODO) To run the agent simulator demo::

    python -m zof.demo.agent_simulator --help

.. (TODO) To run the command line tool demo::

    python -m zof.demo.ofctl --help
