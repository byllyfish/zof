import unittest
import timeit
import pickle
from zof.objectview import from_json


def _test_performance(data):
    stmt = '''from_json("""%s""")''' % data
    result = timeit.timeit(
        stmt, setup='from zof.objectview import from_json', number=10000)
    print('test_from_json_speed=%r' % result)

    try:
        result = timeit.timeit(
            stmt, setup='from ujson import loads as from_json', number=10000)
        print('test_ujson_speed=%r' % result)
    except ModuleNotFoundError:
        pass

    obj = from_json(data)
    data = pickle.dumps(data)
    stmt = '''pickle.loads(%r)''' % data
    result = timeit.timeit(stmt, setup='import pickle', number=10000)
    print('test_pickle_speed=%r' % result)


class JsonTestCase(unittest.TestCase):
    def test_from_json(self):
        obj = from_json('{"b":2}')
        self.assertEqual(obj, {'b': 2})

        obj = from_json(b'{"a":1}')
        self.assertEqual(obj, {'a': 1})

    @unittest.skip("skip speed test")
    def test_from_json_speed(self):
        # Original PacketIn message
        data = '{"params":{"type":"PACKET_IN","time":"1506453847.618103000","xid":344,"version":1,"conn_id":3,"datapath_id":"00:00:00:00:00:00:00:01","msg":{"buffer_id":343,"total_len":64,"in_port":1,"in_phy_port":0,"metadata":0,"reason":"TABLE_MISS","table_id":0,"cookie":0,"match":[],"data":"8000000000010056010000010800450000320000000040FFF72CC0A80028C0A801287A18586B110897F519E2657E07CC31C311C7C40C8B955151335451D50036","_pkt":[{"field":"ETH_DST","value":"80:00:00:00:00:01"},{"field":"ETH_SRC","value":"00:56:01:00:00:01"},{"field":"ETH_TYPE","value":2048},{"field":"IP_DSCP","value":0},{"field":"IP_ECN","value":0},{"field":"IP_PROTO","value":255},{"field":"IPV4_SRC","value":"192.168.0.40"},{"field":"IPV4_DST","value":"192.168.1.40"},{"field":"NX_IP_TTL","value":64},{"field":"X_PKT_POS","value":34}]}},"method":"OFP.MESSAGE"}'
        _test_performance(data)

        # Smaller JSON
        data = '{"params":{"type":"PACKET_IN","time":"1506453847.618103000","xid":344,"version":1,"conn_id":3,"msg":{"buffer_id":343,"total_len":64,"in_port":1,"metadata":0,"reason":"TABLE_MISS","table_id":0,"cookie":0,"data":"8000000000010056010000010800450000320000000040FFF72CC0A80028C0A801287A18586B110897F519E2657E07CC31C311C7C40C8B955151335451D50036","_pkt":[{"field":"ETH_DST","value":"80:00:00:00:00:01"},{"field":"ETH_SRC","value":"00:56:01:00:00:01"},{"field":"ETH_TYPE","value":2048},{"field":"IP_PROTO","value":255},{"field":"IPV4_SRC","value":"192.168.0.40"},{"field":"IPV4_DST","value":"192.168.1.40"},{"field":"X_PKT_POS","value":34}]}},"method":"OFP.MESSAGE"}'
        _test_performance(data)

        # Smaller and Flatter JSON
        data = '{"params":{"type":"PACKET_IN","time":"1506453847.618103000","xid":344,"version":1,"conn_id":3,"msg":{"buffer_id":343,"total_len":64,"in_port":1,"metadata":0,"reason":"TABLE_MISS","table_id":0,"cookie":0,"data":"8000000000010056010000010800450000320000000040FFF72CC0A80028C0A801287A18586B110897F519E2657E07CC31C311C7C40C8B955151335451D50036","ETH_DST":"80:00:00:00:00:01","ETH_SRC":"00:56:01:00:00:01","ETH_TYPE":2048,"IP_PROTO":255,"IPV4_SRC":"192.168.0.40","IPV4_DST":"192.168.1.40","X_PKT_POS":34}},"method":"OFP.MESSAGE"}'
        _test_performance(data)
