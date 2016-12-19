import string
import textwrap


class CompiledMessage(object):
    """Concrete class representing a compiled OpenFlow message template.

    Attributes:
        _app (ControllerApp): App object.
        _template (StringTemplate): Prepared message template.
    """

    def __init__(self, app, msg):
        self._app = app
        self._template = None
        self._compile(msg)

    def send(self, **kwds):
        self._app.send(self._template, kwds)


    def request(self, **kwds):
        return self._app.request(self._template, kwds)


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



_TEMPLATE = """\
method: OFP.SEND
params:
  xid: $xid
  datapath_id: $datapath_id
  conn_id: $conn_id
  %s"""
