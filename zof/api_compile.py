import string
import textwrap
import asyncio
import logging
from .controller import Controller
from .objectview import ObjectView, to_json
from .pktview import pktview_to_list

LOGGER = logging.getLogger(__package__)

_TEMPLATE = """\
method: OFP.SEND
params:
  xid: $xid
  datapath_id: $datapath_id
  conn_id: $conn_id
  %s"""


# pylint: disable=redefined-builtin
def compile(msg):
    """Compile an OpenFlow message template."""
    controller = Controller.singleton()
    if isinstance(msg, str):
        return CompiledMessage(controller, msg)
    return CompiledObject(controller, msg)


class CompiledMessage(object):
    """Concrete class representing a compiled OpenFlow message template.

    Attributes:
        _controller (Controller): Controller object.
        _template (StringTemplate): Prepared message template.
    """

    def __init__(self, controller, msg):
        assert isinstance(msg, str)
        self._controller = controller
        self._template = None
        self._template_args = None
        self._compile(msg)

    def send(self, **kwds):
        """Send an OpenFlow message (fire and forget).

        Args:
            kwds (dict): Template argument values.
        """
        kwds.setdefault('xid', self._controller.next_xid())
        self._controller.write(self._complete(kwds, _task_locals()))

    def request(self, **kwds):
        """Send an OpenFlow request and receive a response.

        Args:
            kwds (dict): Template argument values.
        """
        xid = kwds.setdefault('xid', self._controller.next_xid())
        return self._controller.write(
            self._complete(kwds, _task_locals()), xid)

    def _compile(self, msg):
        """Compile OFP.SEND message and store it into `self._template`.

        Args:
            msg (str): YAML message.
        """
        # Remove top-level indent.
        msg = textwrap.dedent(msg).strip()
        # Add indent of 2 spaces.
        msg = msg.replace('\n', '\n  ')
        self._template = MyTemplate(_TEMPLATE % msg)
        self._template_args = self._template.args()

    def _complete(self, kwds, task_locals):
        """Substitute keywords into OFP.SEND template.

        Translate `bytes` values to hexadecimal and escape all string values.
        """

        dpid = kwds.setdefault('datapath_id', task_locals.get('datapath_id'))
        conn_id = kwds.setdefault('conn_id', task_locals.get('conn_id'))

        if conn_id is None:
            # Either conn_id is not present *or* it's equal to None.
            kwds['conn_id'] = 0
            if not dpid:
                raise ValueError('Must specify either datapath_id or conn_id.')

        for key in kwds:
            val = kwds[key]
            if isinstance(val, bytes):
                kwds[key] = val.hex()
            elif isinstance(val, (str, dict, ObjectView)):
                kwds[key] = to_json(val)
            elif val is None:
                kwds[key] = 'null'

        try:
            self._check(kwds)
            return self._template.substitute(kwds)
        except KeyError as ex:
            error = 'Missing ${%s} argument for %r' % (ex.args[0], self)
        raise LookupError(error)

    def _check(self, kwds):
        """Check kwds against known template vars."""
        for key in kwds:
            if key not in self._template_args:
                raise ValueError('Unknown keyword argument "%s"' % key)

    def __repr__(self):
        """Return string represenation of template."""
        template = self._template.template.replace('\n', '\n  ')
        return 'CompiledMessage ---\n  %s' % template


class CompiledObject(object):
    """Concrete class representing a compiled OpenFlow object template."""

    def __init__(self, controller, obj):
        assert isinstance(obj, (dict, ObjectView))
        assert 'type' in obj
        self._controller = controller
        self._obj = obj
        if self._obj['type'] in ('PACKET_OUT', 'PACKET_IN'):
            self._convert_pkt()

    def send(self, **kwds):
        """Send an OpenFlow message (fire and forget).

        Args:
            kwds (dict): Template argument values.
        """
        kwds.setdefault('xid', self._controller.next_xid())
        self._controller.write(self._complete(kwds, _task_locals()))

    def request(self, **kwds):
        """Send an OpenFlow request and receive a response.

        Args:
            kwds (dict): Template argument values.
        """
        xid = kwds.setdefault('xid', self._controller.next_xid())
        return self._controller.write(
            self._complete(kwds, _task_locals()), xid)

    def _complete(self, kwds, task_locals):
        """Substitute keywords into object template, and compile to JSON.
        """
        kwds.setdefault('datapath_id', task_locals['datapath_id'])
        kwds.setdefault('conn_id', task_locals['conn_id'])

        if 'datapath_id' not in self._obj:
            self._obj['datapath_id'] = kwds['datapath_id']
        if 'xid' not in self._obj:
            self._obj['xid'] = kwds['xid']
        if 'conn_id' not in self._obj and kwds['conn_id'] is not None:
            self._obj['conn_id'] = kwds['conn_id']

        if self._obj['datapath_id'] is None and self._obj.get(
                'conn_id') is None:
            raise ValueError('Must specify either datapath_id or conn_id.')

        # TODO(bfish): Handle conn_id.
        return to_json(dict(method='OFP.SEND', params=self._obj))

    def _convert_pkt(self):
        """Convert high level API `pkt` to low level API."""
        msg = self._obj['msg']
        if 'pkt' in msg:
            msg = msg.copy()
            if 'payload' in msg['pkt']:
                msg['_pkt_data'] = msg['pkt']['payload']
            msg['_pkt'] = pktview_to_list(msg['pkt'])
            del msg['pkt']
            self._obj['msg'] = msg


class MyTemplate(string.Template):
    def args(self):
        """Return set of template arguments."""
        result = set()
        # pylint: disable=no-member
        for m in self.pattern.finditer(self.template):
            named = m.group('named') or m.group('braced')
            if named:
                result.add(named)
        return result


def _task_locals():
    task = asyncio.Task.current_task()
    task_locals = getattr(task, 'ofp_task_locals', {})
    assert isinstance(task_locals, dict)
    return task_locals
