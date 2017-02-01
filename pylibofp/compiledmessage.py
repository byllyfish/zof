import string
import textwrap
import asyncio
from .objectview import ObjectView, to_json
from .event import MatchObject


_TEMPLATE = """\
method: OFP.SEND
params:
  xid: $xid
  datapath_id: $datapath_id
  conn_id: $conn_id
  %s"""


class CompiledMessage(object):
    """Concrete class representing a compiled OpenFlow message template.

    Attributes:
        _parent (Controller): Controller object.
        _template (StringTemplate): Prepared message template.
    """

    def __init__(self, parent, msg):
        assert isinstance(msg, str)
        self._parent = parent
        self._template = None
        self._compile(msg)

    def send(self, **kwds):
        """Send an OpenFlow message (fire and forget).

        Args:
            kwds (dict): Template argument values.
        """
        kwds.setdefault('xid', self._parent.next_xid())
        task_locals = asyncio.Task.current_task().ofp_task_locals
        self._parent.write(self._complete(kwds, task_locals))

    def request(self, **kwds):
        """Send an OpenFlow request and receive a response.

        Args:
            kwds (dict): Template argument values.
        """
        xid = kwds.setdefault('xid', self._parent.next_xid())
        task_locals = asyncio.Task.current_task().ofp_task_locals
        return self._parent.write(self._complete(kwds, task_locals), xid)

    def _compile(self, msg):
        """Compile OFP.SEND message and store it into `self._template`.

        Args:
            msg (str): YAML message.
        """
        # Remove top-level indent.
        msg = textwrap.dedent(msg).strip()
        # Add indent of 2 spaces.
        msg = msg.replace('\n', '\n  ')
        self._template = string.Template(_TEMPLATE % msg)

    def _complete(self, kwds, task_locals):
        """Substitute keywords into OFP.SEND template.

        Translate `bytes` values to hexadecimal and escape all string values.
        """

        kwds.setdefault('datapath_id', task_locals['datapath_id'])
        kwds.setdefault('conn_id', task_locals['conn_id'])

        if kwds.get('conn_id') is None:
            # Either conn_id is not present *or* it's equal to None.
            kwds['conn_id'] = 0
            if not kwds['datapath_id']:
                raise ValueError('Must specify either datapath_id or conn_id.')

        for key in kwds:
            val = kwds[key]
            if isinstance(val, bytes):
                kwds[key] = val.hex()
            elif isinstance(val, (str, dict, ObjectView)):
                kwds[key] = to_json(val)
            elif val is None:
                kwds[key] = 'null'

        return self._template.substitute(kwds)


class CompiledObject(object):
    """Concrete class representing a compiled OpenFlow object template."""

    def __init__(self, parent, obj):
        assert isinstance(obj, (dict, ObjectView))
        assert 'type' in obj
        self._parent = parent
        self._obj = obj
        if self._obj['type'] in ('PACKET_OUT', 'PACKET_IN'):
            self._convert_pkt()

    def send(self, **kwds):
        """Send an OpenFlow message (fire and forget).

        Args:
            kwds (dict): Template argument values.
        """
        kwds.setdefault('xid', self._parent.next_xid())
        task_locals = asyncio.Task.current_task().ofp_task_locals
        self._parent.write(self._complete(kwds, task_locals))

    def request(self, **kwds):
        """Send an OpenFlow request and receive a response.

        Args:
            kwds (dict): Template argument values.
        """
        xid = kwds.setdefault('xid', self._parent.next_xid())
        task_locals = asyncio.Task.current_task().ofp_task_locals
        return self._parent.write(self._complete(kwds, task_locals), xid)

    def _complete(self, kwds, task_locals):
        """Substitute keywords into object template, and compile to JSON.
        """
        kwds.setdefault('datapath_id', task_locals['datapath_id'])
        kwds.setdefault('conn_id', task_locals['conn_id'])

        if not 'datapath_id' in self._obj:
            self._obj['datapath_id'] = kwds['datapath_id']
        if not 'xid' in self._obj:
            self._obj['xid'] = kwds['xid']

        # TODO(bfish): Handle conn_id.
        return to_json(dict(method='OFP.SEND', params=self._obj))


    def _convert_pkt(self):
        msg = self._obj['msg']
        if 'pkt' in msg:
            msg = msg.copy()
            msg['_pkt_decode'] = MatchObject.to_list(msg['pkt'])
            del msg['pkt']
            self._obj['msg'] = msg






