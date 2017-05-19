import argparse


class _SplitCommaAction(argparse.Action):
    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        if nargs is not None:
            raise ValueError('nargs not allowed')
        super().__init__(option_strings, dest, **kwargs)
        self._count = 0
    def __call__(self, parser, namespace, values, option_string=None):
        self._count += 1
        if self._count > 1:
            raise argparse.ArgumentError(self, 'Option present more than once')
        values = [s.strip() for s in values.split(',')]
        setattr(namespace, self.dest, values)


def ofp_default_args():
    """Construct default ArgumentParser parent.
    """
    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_argument_group('common arguments')
    group.add_argument(
        '--listen-endpoints',
        metavar='ENDPOINT,...',
        action=_SplitCommaAction,
        help='listen endpoints separated by commas')
    group.add_argument('--loglevel', metavar='LEVEL', help='log level')
    group.add_argument('--logfile', metavar='FILE', help='log file')
    return parser
