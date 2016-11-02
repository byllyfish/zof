import unittest
from pylibofp.event import load_event, Event


class LoadEventTestCase(unittest.TestCase):

    def test_empty(self):
        # Loading empty bytes is an error.
        event = load_event(b'')
        self.assertEqual('EXCEPTION', event.event)
        self.assertEqual('Expecting value: line 1 column 1 (char 0)', event.reason)

        # Loading only white space is an error.
        event = load_event(b'  ')
        self.assertEqual('EXCEPTION', event.event)
        self.assertEqual('Expecting value: line 1 column 3 (char 2)', event.reason)

    def test_empty_dict(self):
        # Test empty event as bytes.
        event = load_event(b'{}')
        self.assertIsInstance(event, Event)
        self.assertEqual(event, {})

    def test_empty_dict2(self):
        # Test empty event as unicode str.
        event = load_event('{}')
        self.assertIsInstance(event, Event)
        self.assertEqual(event, {})

    def test_empty_dict3(self):
        # Test empty event with extra whitespace.
        event = load_event(b' {} \n')
        self.assertIsInstance(event, Event)
        self.assertEqual(event, {})

    def test_empty_dict_multiple(self):
        # Test that multiple empty events fail.
        event = load_event(b'{}{}')
        self.assertEqual('EXCEPTION', event.event)
        self.assertEqual('Extra data: line 1 column 3 (char 2)', event.reason)

    def test_truncated_input(self):
        # Test that truncated input is detected.
        event = load_event(b'{ ')
        self.assertEqual('EXCEPTION', event.event)
        self.assertEqual('Expecting property name enclosed in double quotes: line 1 column 3 (char 2)', event.reason)

    def test_other_value(self):
        # Test that non-mapping objects still work.
        event = load_event(b'[1, 2, 3]')
        self.assertIsInstance(event, list)
        self.assertEqual(event, [1, 2, 3])

    def test_utf8(self):
        # Test that Unicode/UTF-8 works.
        data = load_event(b'{"x":"\xe2\x82\xac\xf0\x90\x8c\x82\xf4\x8f\xbf\xbd"}')
        self.assertIsInstance(data, Event)
        self.assertEqual(data, {'x': '\u20AC\U00010302\U0010fffd'})

    def test_event_data(self):
        # Test that `data` is converted from hexadecimal to binary.
        event = load_event(b'{"data":"deadbeef"}')
        self.assertEqual(event, {'data': b'\xde\xad\xbe\xef'})
        # Non-hex data should raise an exception.
        event = load_event(b'{"data":"nonhex"}')
        self.assertEqual('EXCEPTION', event.event)
        self.assertTrue(event.reason.startswith('non-hexadecimal number found'))

    def test_event_pkt_decode(self):
        # Test that `_pkt_decode` lists are converted to dictionaries.
        event = load_event(b'{"data": "ff", "_pkt_decode": [{"field":"a", "value":1}]}')
        self.assertEqual(event.pkt, {'a': 1})
        self.assertFalse("_pkt_decode" in event)
        # _pkt_decode requires the `data` value, otherwise it's not translated
        event = load_event(b'{"_pkt_decode": [{"field":"a", "value":1}]}')
        self.assertFalse("pkt" in event)
        self.assertTrue("_pkt_decode" in event)

    def test_event_str(self):
        # Test that str(event) produces the expected json.
        event = load_event(b'{"foo":"bar"}')
        s = str(event)
        self.assertEqual(s, '{"foo":"bar"}')

    def test_json_dumps(self):
        # Test that event.json_dumps also works.
        event = load_event(b'{"foo":"bar"}')
        s = event.json_dumps(event)
        self.assertEqual(s, '{"foo":"bar"}')

