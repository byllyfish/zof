PYLIBOFP: OpenFlow App Framework
================================

Pylibofp is a Python framework for creating OpenFlow controllers, agents, and other tools.

.. (TODO) architecture image of app with framework, oftr, switches

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

    # Create virtual environment and install pylibofp.
    python3.5 -m venv myenv
    source myenv/bin/activate
    pip install pylibofp


Demos
-----

To run the controller demo::

    python -m pylibofp.demo.layer2_controller --help


.. (TODO) To run the agent simulator demo::

    python -m pylibofp.demo.agent_simulator --help

.. (TODO) To run the command line tool demo::

    python -m pylibofp.demo.ofctl --help
