import unittest
from zof.endpoint import Endpoint


class EndpointTestCase(unittest.TestCase):
    def test_ipv4(self):
        endpt = Endpoint('127.0.0.1:80')
        self.assertEqual(str(endpt), '127.0.0.1:80')
        self.assertEqual(endpt.host, '127.0.0.1')
        self.assertEqual(endpt.port, 80)

    def test_ipv6(self):
        endpt = Endpoint('[::1]:81')
        self.assertEqual(str(endpt), '[::1]:81')
        self.assertEqual(endpt.host, '::1')
        self.assertEqual(endpt.port, 81)

    def test_port_only(self):
        endpt = Endpoint('82')
        self.assertEqual(str(endpt), ':82')
        self.assertEqual(endpt.host, '')
        self.assertEqual(endpt.port, 82)

        endpt = Endpoint(':82')
        self.assertEqual(str(endpt), ':82')
        self.assertEqual(endpt.host, '')
        self.assertEqual(endpt.port, 82)

        endpt = Endpoint('[]:82')
        self.assertEqual(str(endpt), ':82')
        self.assertEqual(endpt.host, '')
        self.assertEqual(endpt.port, 82)

    def test_invalid(self):
        subtests = [' :101', ':102 ']
        for subtest in subtests:
            with self.subTest(subtest=subtest):
                with self.assertRaises(ValueError):
                    Endpoint(subtest)
