CHANGELOG
=========


Version 0.4.1
-------------

- Fix exception in datapath service caused by manually closed datapath.
- All fields support slash notation.
- zof.run() supports arguments passed as a list.
- Fixed zof.encode() function to support dict and ObjectView argument types.
- Fixed zof.encode() function so exception messages are strings, not bytes.


Version 0.4.0
-------------

- Exceptions in async tasks will be associated with the app that created the task.
- Add get() method to PktView.
- Added zof.encode() function.
- Added --sim-endpoint command line argument to simulator demo app.
- Handle failure in datapath service _get_ports() function.


Version 0.3.1
-------------

- Fix UDP tp_src/tp_dst bug in convert_from_ofctl.


Version 0.3.0
-------------

- Rename to zof.
- Add close() method to Datapath class for hanging up.
- Change default log format.
- Metrics app now initiates on prestart event.
- Add zof.demo.hub module.


Version 0.2.0
-------------

- Add the set_apps function.
- Datapath service adds 'datapath' property to all message events.
- Add 'src' and 'dst' read-only properties to PktView.
- Add 'port_up' metric.
- Support slash notation in IPV6_ND_TARGET, IPV6_ND_SLL, and IPV6_ND_TLL fields.


Version 0.1.1
-------------

- Fix bug in datapath service.


Version 0.1.0
-------------

- Initial release.
