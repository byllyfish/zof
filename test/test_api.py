import unittest
from zof import Application
from zof.controller import Controller


class TestApi(unittest.TestCase):
    def tearDown(self):
        Controller.destroy()

    def test_zof(self):
        app1 = Application('app1', exception_fatal=True, precedence=12)
        self.assertEqual(app1.name, 'app1')

        app2 = Application('app2', precedence=5001)
        self.assertEqual(app2.name, 'app2')

        self.assertEqual(app1.apps, app2.apps)

        # Test that apps are sorted by precedence.
        self.assertEqual(app1.apps, [app2, app1])

    def test_duplicate_name(self):
        # Do not allow two apps to have the same name.
        Application('app3')
        with self.assertRaises(ValueError):
            Application('app3')
