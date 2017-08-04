import unittest
from zof.datapath import DatapathList, normalize_datapath_id, normalize_port_no


class DatapathTestCase(unittest.TestCase):
    def test_datapath_list(self):
        dpids = DatapathList()
        dp1 = dpids.add_datapath(
            datapath_id='00:00:00:00:00:00:00:01',
            conn_id=1)
        dp2 = dpids.add_datapath(
            datapath_id='00:00:00:00:00:00:00:02',
            conn_id=2)
        self.assertEqual(len(dpids), 2)

        port1 = dp1.add_port(port_no=1)
        port2 = dp1.add_port(port_no=2)
        port3 = dp1.add_port(port_no='LOCAL')
        self.assertEqual(len(dp1), 3)

        ports = [port for port in dp1]
        self.assertEqual(ports, [port1, port2, port3])

        self.assertEqual(dp1.datapath_id, '00:00:00:00:00:00:00:01')
        self.assertEqual(port1.datapath_id, '00:00:00:00:00:00:00:01')
        self.assertIs(port1.datapath, dp1)
        self.assertEqual(port1.port_no, 1)

        dpids.delete_datapath(datapath_id=dp1.datapath_id)
        self.assertEqual(len(dpids), 1)

        dps = [dp for dp in dpids]
        self.assertEqual(dps, [dp2])

    def test_normalize_datapath(self):
        dpid = normalize_datapath_id('00:00:00:00:00:00:00:01')
        self.assertEqual(dpid, 1)

        dpid = normalize_datapath_id('ff:ff:ff:ff:ff:ff:ff:ff')
        self.assertEqual(dpid, 2**64-1)

        dpid = normalize_datapath_id(0x12345)
        self.assertEqual(dpid, 0x12345)

        dpid = normalize_datapath_id('0x567')
        self.assertEqual(dpid, 0x567)

        with self.assertRaises(ValueError):
            normalize_datapath_id('blah')

    def test_normalize_port_no(self):
        port_no = normalize_port_no(123)
        self.assertEqual(port_no, 123)

        port_no = normalize_port_no('0x123')
        self.assertEqual(port_no, 0x123)

        port_no = normalize_port_no('LOCAL')
        self.assertEqual(port_no, 'LOCAL')

        port_no = normalize_port_no('controller')
        self.assertEqual(port_no, 'CONTROLLER')
