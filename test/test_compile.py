import unittest
import zof


class CompileTestCase(unittest.TestCase):
    def test_compile_string(self):
        """Test that a YAML string compiles to an OF message.
        """
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
        """Test that an object compiles to an OF message.
        """
        ofmsg = zof.compile({'type': 'HELLO'})
        self.assertEqual('''\
<zof.CompiledObject>
{
    "type": "HELLO"
}
</zof.CompiledObject>''', repr(ofmsg))

    def test_compile_object_packetout(self):
        """Test that an object of type PACKET_IN/OUT compiles to an OF message.
        """
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

    def test_compile_rpc_object(self):
        """Test that an object compiles to an OF message.
        """
        rpc_msg = zof.compile({'method': 'OFP.DESCRIPTION'})
        self.assertEqual('''\
<zof.CompiledObjectRPC>
{
    "method": "OFP.DESCRIPTION"
}
</zof.CompiledObjectRPC>''', repr(rpc_msg))
