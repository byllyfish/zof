import unittest
import zof


class CompileTestCase(unittest.TestCase):

    def test_compile_string(self):
        ofmsg = zof.compile('type: HELLO')
        self.assertEqual('''\
<zof.CompiledString args=['conn_id', 'datapath_id', 'xid']>
method: OFP.SEND
params:
  xid: $xid
  datapath_id: $datapath_id
  conn_id: $conn_id
  type: HELLO
</zof.CompiledString>''', repr(ofmsg))

    def test_compile_object(self):
        ofmsg = zof.compile({'type': 'HELLO'})
        self.assertEqual('''\
<zof.CompiledObject>
{
    "type": "HELLO"
}
</zof.CompiledObject>''', repr(ofmsg))

    def test_compile_object_packetout(self):
        ofmsg = zof.compile({
            'type': 'PACKET_OUT',
            'msg': {
                'pkt': {
                    'eth_type': 0x0800
                }
            }
        })
        self.assertEqual('''\
<zof.CompiledObject>
{
    "msg": {
        "_pkt": [
            {
                "field": "ETH_TYPE",
                "value": 2048
            }
        ]
    },
    "type": "PACKET_OUT"
}
</zof.CompiledObject>''', repr(ofmsg))
