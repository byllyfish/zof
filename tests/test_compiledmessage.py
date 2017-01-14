import unittest
from pylibofp.compiledmessage import CompiledMessage


class CompiledMessageTestCase(unittest.TestCase):

    def test_init(self):
        msg = '''
        type: ECHO_REQUEST
        msg:
          data: DEADBEEF
        '''
        cmsg = CompiledMessage(None, msg)

        expected = '''\
method: OFP.SEND
params:
  xid: $xid
  datapath_id: $datapath_id
  conn_id: $conn_id
  type: ECHO_REQUEST
  msg:
    data: DEADBEEF'''

        actual = cmsg._template.template
        self.assertEqual(expected, actual)

        task_locals = dict(datapath_id = 'dpid_1', conn_id=7)

        expected = '''\
method: OFP.SEND
params:
  xid: 1000
  datapath_id: "dpid_1"
  conn_id: 7
  type: ECHO_REQUEST
  msg:
    data: DEADBEEF'''

        actual = cmsg._complete(dict(xid=1000), task_locals)
        self.assertEqual(expected, actual)

