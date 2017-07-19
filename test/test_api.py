import unittest
from ofp_app import Application
from ofp_app.controller import Controller


class TestApi(unittest.TestCase):

    def tearDown(self):
        Controller.destroy()


    def test_ofp_app(self):
        app1 = Application('app1', kill_on_exception=True, precedence=5001)
        self.assertEqual(app1.name, 'app1')

        app2 = Application('app2', precedence=12)
        self.assertEqual(app2.name, 'app2')

        self.assertEqual(app1.apps, app2.apps)

        # Test that apps are sorted by precedence.
        self.assertEqual(app1.apps, [app2, app1])


    def test_duplicate_name(self):
        # Do not allow two apps to have the same name.
        app3 = Application('app3')
        with self.assertRaises(ValueError):
            app4 = Application('app3')
