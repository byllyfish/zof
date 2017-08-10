import unittest
import zof


class TestApi(unittest.TestCase):

    def test_zof(self):
        zof.set_apps([])

        app1 = zof.Application('app1', exception_fatal=True, precedence=12)
        self.assertEqual(app1.name, 'app1')

        app2 = zof.Application('app2', precedence=5001)
        self.assertEqual(app2.name, 'app2')

        # Do not allow two apps to have the same name.
        app3 = zof.Application('app3')
        with self.assertRaises(ValueError):
            zof.Application('app3')

        # Test that apps are sorted by precedence.
        self.assertEqual(zof.get_apps(), [app2, app3, app1])
