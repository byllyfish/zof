import unittest
import os
from pylibofp.controller import Controller
from pylibofp.objectview import ObjectView

DIR = os.path.dirname(os.path.abspath(__file__))

def mydir(name):
    return os.path.join(DIR, name)


class ControllerTestCase(unittest.TestCase):

    def test_init_missing_file(self):
        with self.assertRaisesRegex(FileNotFoundError, 'No such file'):
            Controller(config_file=mydir('missing.json'))

    def test_init_empty_file(self):
        with self.assertRaisesRegex(ValueError, 'Expecting value'):
            Controller(config_file=mydir('empty.json'))

    def test_init_none_file(self):
        c = Controller(config_file=None)
        config = c.config
        self.assertIsInstance(config, ObjectView)
        self.assertIsInstance(config.apps, list)
        self.assertIsInstance(config.connect, list)
        self.assertIsInstance(config.listen, list)

    def test_init_mock_file(self):
        c = Controller(config_file=mydir('mock.json'))
        config = c.config
        self.assertIsInstance(config, ObjectView)
        self.assertIsInstance(config.apps, list)
        self.assertIsInstance(config.connect, list)
        self.assertIsInstance(config.listen, list)

