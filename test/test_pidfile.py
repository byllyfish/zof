import unittest
import os
import tempfile
from zof.pidfile import PidFile


def _tmp_path():
    path = tempfile.gettempdir()
    return os.path.join(path, 'zof-pidfile-test')


class PidFileTestCase(unittest.TestCase):
    def test_pidfile(self):
        path = _tmp_path()
        pidfile = PidFile(path)
        pidfile.write()

        self.assertEqual(pidfile.read(), os.getpid())

        pidfile.remove()
        # Test that it's removed.
        self.assertFalse(os.path.exists(path))

    def test_context_mgr(self):
        path = _tmp_path()
        with PidFile(path):
            pid = PidFile(path).read()
            self.assertEqual(pid, os.getpid())
