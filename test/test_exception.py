import unittest
from zof.event import make_event
import zof.exception as _exc


class ExceptionTestCase(unittest.TestCase):
    def test_timeout(self):
        ex = _exc.TimeoutException(1, 5)
        self.assertEqual(ex.xid, 1)
        self.assertEqual(ex.timeout, 5)
        self.assertEqual(ex.message, '')
        self.assertEqual(str(ex), '[TimeoutException xid=1 timeout=5]')

    def test_rpc(self):
        event = make_event(id=2, error={'message': 'm', 'code': 1000})
        ex = _exc.RPCException(event)
        self.assertEqual(ex.xid, 2)
        self.assertEqual(ex.message, 'm')
        self.assertEqual(ex.code, 1000)
        self.assertEqual(str(ex), '[RPCException xid=2 message=m]')

    def test_error(self):
        event = make_event(xid=3, type='ERROR', msg={})
        ex = _exc.ErrorException(event)
        self.assertEqual(ex.xid, 3)
        self.assertIs(ex.event, event)
        self.assertRegex(str(ex), r'\[ErrorException xid=3 event=.+\]')

    def test_delivery(self):
        event = make_event(xid=4, type='FLOW_MOD', msg={})
        ex = _exc.DeliveryException(event)
        self.assertEqual(ex.xid, 4)
        self.assertIs(ex.event, event)
        self.assertRegex(str(ex), r'\[DeliveryException xid=4 event=.+\]')
