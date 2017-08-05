import unittest
from zof.datapath import DatapathList, Datapath, normalize_datapath_id, normalize_port_no
from zof.objectview import make_objectview


class DatapathTestCase(unittest.TestCase):
    def test_datapath_list(self):
        dpids = DatapathList()
        self.assertFalse(dpids)
        self.assertEqual(len(dpids), 0)

        dp1 = dpids.add_datapath(
            datapath_id='00:00:00:00:00:00:00:01', conn_id=1)
        dp2 = dpids.add_datapath(
            datapath_id='00:00:00:00:00:00:00:02', conn_id=2)
        self.assertTrue(dpids)
        self.assertEqual(len(dpids), 2)
        self.assertIs(dpids[0x01], dp1)
        self.assertIs(dpids['2'], dp2)

        dpids.delete_datapath(datapath_id=dp1.datapath_id)
        self.assertEqual(len(dpids), 1)

        dps = [dp for dp in dpids]
        self.assertEqual(dps, [dp2])

    def test_datapath(self):
        dp1 = Datapath(datapath_id='00:00:00:00:00:00:00:01', conn_id=1001)
        self.assertEqual(dp1.datapath_id, '00:00:00:00:00:00:00:01')
        self.assertEqual(dp1.conn_id, 1001)
        self.assertTrue(dp1)  # Empty datapath is still "true"

        port1 = dp1.add_port(port_no=1)
        port2 = dp1.add_port(port_no=2)
        port3 = dp1.add_port(port_no='LOCAL')
        self.assertEqual(len(dp1), 3)

        self.assertIs(dp1['2'], port2)
        self.assertIs(dp1['local'], port3)

        ports = [port for port in dp1]
        self.assertEqual(ports, [port1, port2, port3])

        self.assertEqual(port1.datapath_id, '00:00:00:00:00:00:00:01')
        self.assertIs(port1.datapath, dp1)
        self.assertEqual(port1.port_no, 1)

    def test_port(self):
        dp1 = Datapath(datapath_id='00:00:00:00:00:00:00:01', conn_id=1001)
        port1 = dp1.add_port(port_no=1)

        self.assertEqual(port1.port_no, 1)
        self.assertIs(port1.datapath, dp1)
        self.assertTrue(port1.up)
        self.assertFalse(port1.admin_down)

    def test_add_datapath(self):
        dpids = DatapathList()

        # add_datapath is idempotent, if values are identical.
        dp1 = dpids.add_datapath(datapath_id=0x01, conn_id=0x02)
        dp2 = dpids.add_datapath(datapath_id=0x01, conn_id=0x02)
        self.assertEqual(len(dpids), 1)
        self.assertIs(dp2, dp1)

        with self.assertRaises(ValueError):
            # add_datapath fails if conn_id values differ
            dpids.add_datapath(datapath_id=0x01, conn_id=0x03)

        # We don't check that conn_id is unique.
        dp3 = dpids.add_datapath(datapath_id=0x02, conn_id=0x02)
        self.assertIsNot(dp3, dp1)

    def test_delete_datapath(self):
        dpids = DatapathList()
        dp1 = dpids.add_datapath(datapath_id=0x01, conn_id=0x01)
        dp2 = dpids.add_datapath(datapath_id=0x02, conn_id=0x02)

        result = dpids.delete_datapath(datapath_id=1)
        self.assertIs(result, dp1)
        self.assertEqual(len(dpids), 1)
        result = dpids.delete_datapath(datapath_id=1)
        self.assertIsNone(result)

        result = dpids.delete_datapath(datapath_id=dp2.datapath_id)
        self.assertIs(result, dp2)
        self.assertEqual(len(dpids), 0)

        result = dpids.delete_datapath(datapath_id=12345)
        self.assertIsNone(result)

    def test_add_port(self):
        dp1 = Datapath(datapath_id='00:00:00:00:00:00:00:01', conn_id=1001)

        # add_port is idempotent if port_no's are identical.
        port1 = dp1.add_port(port_no=1)
        port2 = dp1.add_port(port_no=1)
        self.assertEqual(len(dp1), 1)
        self.assertIs(port1, port2)

    def test_delete_port(self):
        dp1 = Datapath(datapath_id='00:00:00:00:00:00:00:01', conn_id=1001)
        port1 = dp1.add_port(port_no=1)
        port2 = dp1.add_port(port_no=2)

        result = dp1.delete_port(port_no=1)
        self.assertIs(result, port1)
        self.assertEqual(len(dp1), 1)
        result = dp1.delete_port(port_no=1)
        self.assertIsNone(result)

        result = dp1.delete_port(port_no=2)
        self.assertIs(result, port2)
        self.assertEqual(len(dp1), 0)

        result = dp1.delete_port(port_no=12345)
        self.assertIsNone(result)

    def test_add_ports(self):
        dp1 = Datapath(datapath_id='00:00:00:00:00:00:00:01', conn_id=1001)
        port1_desc = make_objectview({
            'port_no': 9,
            'hw_addr': '00:00:00:00:00:01',
            'name': 'Port 1',
            'state': ['LINK_DOWN'],
            'config': ['PORT_DOWN']
        })
        dp1.add_ports([port1_desc])

        port1 = dp1[9]
        self.assertEqual(port1.port_no, 9)
        self.assertEqual(port1.hw_addr, '00:00:00:00:00:01')
        self.assertEqual(port1.name, 'Port 1')
        self.assertFalse(port1.up)
        self.assertTrue(port1.admin_down)

    def test_normalize_datapath(self):
        dpid = normalize_datapath_id('00:00:00:00:00:00:00:01')
        self.assertEqual(dpid, 1)

        dpid = normalize_datapath_id('ff:ff:ff:ff:ff:ff:ff:ff')
        self.assertEqual(dpid, 2**64 - 1)

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
