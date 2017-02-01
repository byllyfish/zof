import unittest
from pylibofp.compiledmessage import CompiledMessage
from pylibofp.objectview import ObjectView


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


    def test_dict_var(self):
        template = '''
        type: $type_
        msg: $msg
        '''
        cmsg = CompiledMessage(None, template)
        task_locals = dict(datapath_id=None, conn_id=None)

        expected = '''\
method: OFP.SEND
params:
  xid: 1
  datapath_id: null
  conn_id: 13
  type: "ECHO_REQUEST"
  msg: {"data":"414243444546"}'''

        # Test with msg as a dictionary.
        msg = dict(data=b'ABCDEF')
        actual = cmsg._complete(dict(xid=1, conn_id=13, type_='ECHO_REQUEST', msg=msg), task_locals)
        self.assertEqual(expected, actual)

        # Test with msg as an ObjectView.
        msg = ObjectView(msg)
        actual = cmsg._complete(dict(xid=1, conn_id=13, type_='ECHO_REQUEST', msg=msg), task_locals)
        self.assertEqual(expected, actual)
