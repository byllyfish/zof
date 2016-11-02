import sys
if sys.version_info < (3, 4, 2):
    raise NotImplementedError("Requires Python version 3.4.2 or later.")

import unittest

# `python3 tests` will run all tests. 
# (Alternatively, use `python3 -m unittest discover`.)

loader = unittest.defaultTestLoader.discover('.')
unittest.TextTestRunner(verbosity=2).run(loader)

