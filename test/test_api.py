import unittest
import zof
from zof.controller import Controller


class TestApi(unittest.TestCase):
    def tearDown(self):
        Controller.destroy()

    def test_zof(self):
        app1 = zof.Application('app1', exception_fatal=True, precedence=12)
        self.assertEqual(app1.name, 'app1')

        app2 = zof.Application('app2', precedence=5001)
        self.assertEqual(app2.name, 'app2')

        # Test that apps are sorted by precedence.
        self.assertEqual(zof.get_apps(), [app2, app1])

    def test_duplicate_name(self):
        # Do not allow two apps to have the same name.
        zof.Application('app3')
        with self.assertRaises(ValueError):
            zof.Application('app3')

    def test_init_exclusions(self):
        # These functions should fail if the system is in INIT mode.
        with self.assertRaises(RuntimeError):
            zof.post_event('test')
