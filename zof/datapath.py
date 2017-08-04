from collections import OrderedDict


class DatapathList:
    """Represents a collection of datapaths."""

    def __init__(self):
        self._datapaths = OrderedDict()

    def add_datapath(self, *, datapath_id, conn_id, endpoint):
        dpid_key = normalize_dpid_key(datapath_id)
        datapath = Datapath(datapath_id, conn_id, endpoint)
        self._datapaths[dpid_key] = datapath
        return datapath

    def get_datapath(self, *, datapath_id):
        dpid_key = normalize_dpid_key(datapath_id)
        return self._datapaths[dpid_key]

    def delete_datapath(self, *, datapath_id):
        dpid_key = normalize_dpid_key(datapath_id)
        datapath = self._datapaths.pop(dpid_key)
        return datapath

    def __len__(self):
        return len(self._datapaths)

    def __iter__(self):
        return iter(self._datapaths.values())


class Datapath:
    """Represents a datapath."""

    def __init__(self, datapath_id, conn_id, endpoint):
        self.datapath_id = datapath_id
        self.conn_id = conn_id
        self.endpoint = endpoint
        self.ports = OrderedDict()

    def add_port(self, *, port_no):
        """Add port to datapath.

        Returns:
            Port: port object
        """
        port_no = normalize_port_no(port_no)
        port = Port(port_no, datapath=self)
        self.ports[port_no] = port
        return port

    def get_port(self, *, port_no):
        """Return existing port.
        """
        port_no = normalize_port_no(port_no)
        return self.ports[port_no]

    def delete_port(self, *, port_no):
        """Remove port from datapath.
        """
        port_no = normalize_port_no(port_no)
        port = self.ports.pop(port_no)
        return port

    def __getstate__(self):
        return self.__dict__

    def __len__(self):
        return len(self.ports)

    def __iter__(self):
        return iter(self.ports.values())


class Port:
    """Represents a datapath port."""

    def __init__(self, port_no, datapath):
        self.datapath = datapath
        self.port_no = port_no
        self.state = []

    def __getstate__(self):
        return self.__dict__

    @property
    def datapath_id(self):
        return self.datapath.datapath_id


def normalize_dpid_key(datapath_id):
    """Normalize datapath_id value."""
    if isinstance(datapath_id, int):
        return datapath_id
    if isinstance(datapath_id, str):
        return int(datapath_id.replace(':', ''), 16)
    raise ValueError('Invalid datapath_id: %r' % datapath_id)


def normalize_port_no(port_no):
    """Normalize port number value to int or string."""
    if isinstance(port_no, int):
        return port_no
    if isinstance(port_no, str):
        try:
            # Convert decimal and hexadecimal port number strings.
            return int(port_no, 0)
        except ValueError:
            return port_no
    raise ValueError('Invalid port_no: %r' % port_no)
