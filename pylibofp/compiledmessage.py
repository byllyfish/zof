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
  %s"""


'''
def _translate_msg_to_event(msg, kwds, xid):
    """
    Helper function to translate an OpenFlow message in string or object format
    to a valid `OFP.SEND` event.

    `msg` may be a YAML string or an object.
    """
    if isinstance(msg, str):
        msg = _translate_msg_str(msg, kwds)
        hdr = ''
        if 'datapath_id' in kwds:
            hdr += 'datapath_id: %s\n' % kwds['datapath_id']
        if xid is not None:
            hdr += 'xid: %d\n' % xid
        msg = hdr + msg
        return 'method: OFP.SEND\nparams:\n  %s' % msg.replace('\n', '\n  ')
    else:
        if 'datapath_id' in kwds:
            msg['datapath_id'] = kwds['datapath_id']
        if xid is not None:
            msg['xid'] = xid
        return dict(method='OFP.SEND', params=msg)


def _translate_msg_str(msg, kwds):
    # Translate `bytes` values to hexadecimal and escape all string values.
    for key in kwds:
        val = kwds[key]
        if isinstance(val, bytes):
            kwds[key] = val.hex()
        elif isinstance(val, str):
            kwds[key] = json.dumps(val)
    return string.Template(textwrap.dedent(msg).strip()).substitute(kwds)
'''
