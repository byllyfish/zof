import unittest
from pylibofp import ofp_app
from pylibofp.controller import Controller


class TestApi(unittest.TestCase):

    def tearDown(self):
        Controller.destroy()


    def test_ofp_app(self):
        app1 = ofp_app('app1', ofversion=[4], kill_on_exception=True, precedence=5001)
        self.assertEqual(app1.name, 'app1')

        app2 = ofp_app('app2', ofversion=[4], precedence=12)
        self.assertEqual(app2.name, 'app2')

        self.assertEqual(app1.all_apps(), app2.all_apps())

        # Test that apps are sorted by precedence.
        self.assertEqual(app1.all_apps(), [app2._app, app1._app])

        
