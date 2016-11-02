import sys

if sys.version_info < (3, 5, 1):
    raise NotImplementedError(
        "pylibofp requires Python version 3.5.1 or later.")
