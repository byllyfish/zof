import unittest
from zof.api_compile import CompiledString
from zof.objectview import ObjectView


class CompiledStringTestCase(unittest.TestCase):
    def test_init(self):
        msg = '''
        type: ECHO_REQUEST
        msg:
          data: DEADBEEF
        '''
        cmsg = CompiledString(None, msg)

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

        task_locals = dict(datapath_id='dpid_1', conn_id=7)

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
        cmsg = CompiledString(None, template)
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
        actual = cmsg._complete(
            dict(xid=1, conn_id=13, type_='ECHO_REQUEST', msg=msg),
            task_locals)
        self.assertEqual(expected, actual)

        # Test with msg as an ObjectView.
        msg = ObjectView(msg)
        actual = cmsg._complete(
            dict(xid=1, conn_id=13, type_='ECHO_REQUEST', msg=msg),
            task_locals)
        self.assertEqual(expected, actual)

    def test_missing_argument(self):
        msg = '''
        type: ECHO_REQUEST
        msg:
          data: DEADBEEF
        '''
        cmsg = CompiledString(None, msg)

        with self.assertRaises(ValueError):
            cmsg._complete(dict(), dict())

    def test_unknown_argument(self):
        msg = '''
        type: ECHO_REQUEST
        msg:
          data: DEADBEEF
        '''
        cmsg = CompiledString(None, msg)
        task_locals = dict(datapath_id='dpid_1', conn_id=7)

        with self.assertRaisesRegex(ValueError,
                                    'Unknown keyword argument "x"'):
            cmsg._complete(dict(x=5), task_locals)
