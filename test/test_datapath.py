import unittest
from zof.datapath import DatapathList


class DatapathTestCase(unittest.TestCase):
    def test_datapath_list(self):
        dpids = DatapathList()
        dp1 = dpids.add_datapath(
            datapath_id='00:00:00:00:00:00:00:01',
            conn_id=1,
            endpoint='127.0.0.1:1000')
        dp2 = dpids.add_datapath(
            datapath_id='00:00:00:00:00:00:00:02',
            conn_id=2,
            endpoint='127.0.0.1:1001')
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
