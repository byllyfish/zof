import os
import sys
import io
import argparse
import warnings
import logging.config
from pylibofp.objectview import ObjectView

LOGGER = logging.getLogger('pylibofp.controller')

OPENFLOW_PORT = 6653

_DEFAULT_VALUES = {
    'apps': [],
    'connect': [],
    'connect_options': ['DEFAULT_CONTROLLER'],
    'listen': [],
    'listen_options': ['DEFAULT_CONTROLLER'],
    'ofversion': [],
    'loglevel': 'info',
    'libofp': [],
    'cert': '',
    'cafile': '',
    'password': '',
    'tls_id': 0
}


def load_config(*, config_file):
    """
    Load configuration from configuration file and command line arguments. 

    Merge in settings specified in command line arguments. Configure logging.
    Return `config` object.
    """

    # Parse command line arguments.
    args = _make_parser().parse_args(sys.argv[1:], namespace=ObjectView({}))

    # When no config file is specified programmatically, check if one was
    # specified on the command line.
    if not config_file and args.config:
        config_reader = args.config
        config_file = str(args.config.name)
    elif config_file:
        config_reader = open(config_file, encoding='utf-8')
    else:
        config_reader = None

    # Load yaml configuration file, if present.
    if config_reader:
        config = _yaml_load(config_reader, object_hook=ObjectView)
        config_reader.close()
    else:
        config = ObjectView({})

    _default_config(config)
    _merge_args(config, args)
    _configure_logging(config)
    if config_file:
        _make_paths_absolute(config, config_file)

    # Save remaining command-line arguments in the `config` object.
    config.apps.extend(args.remainder)
    
    # If no "--connect" or "--listen" specified, default to listen.
    if not config.connect and not config.listen:
        config.listen = [OPENFLOW_PORT]

    # Make sure the config object has the expected types/values. If this fails,
    # there is a bug somewhere.
    _check_invariant(config)

    return config


def _default_config(config):
    """
    Set up config so it has all the expected keys.
    """
    for key, value in _DEFAULT_VALUES.items():
        if key not in config:
            config[key] = value


def _make_paths_absolute(config, config_file):
    """
    Make the paths to the apps absolute. Treat them as relative to the 
    location of `config_file`.
    """
    config_dir = os.path.dirname(os.path.abspath(config_file))
    config.apps = [os.path.join(config_dir, name) for name in config.apps]


def _merge_args(config, args):
    """
    Merge config object and arguments object.

    - List args extend the corresponding value in config.
    - Scalar args replace the corresponding value in config.
    - File args are read() to produce the config value.
    - Ignore config values that are objects.
    """
    for key in config:
        if isinstance(config[key], ObjectView):
            continue
        if key in args and args[key] is not None:
            if isinstance(args[key], io.IOBase):
                config[key] = args[key].read()
            elif isinstance(config[key], list):
                config[key].extend(args[key])
            else:
                config[key] = args[key]


def _configure_logging(config):
    """
    Set up logging based on our config.

    This routine also enables asyncio debug mode if the starting log level is
    debug.
    """
    if config.loglevel.upper() == 'DEBUG':
        os.environ['PYTHONASYNCIODEBUG'] = '1'

    logging.config.dictConfig(_logging_config(config))
    logging.captureWarnings(True)
    warnings.simplefilter('always')


def _make_parser():
    """
    Construct and return our ArgumentParser.
    """
    prog = os.path.basename(sys.argv[0])
    if prog == '__main__.py':
        prog = 'pylibofp'
    description = 'Run one or more pylibofp apps.'
    epilog = '(M) indicates an option may be used more than once.'
    parser = argparse.ArgumentParser(prog=prog, description=description, epilog=epilog)
    parser.add_argument('--connect',
                        help='connect to "host:port" (M)',
                        action='append')
    parser.add_argument('--listen',
                        help='listen on "[host:]port (M)',
                        action='append')
    parser.add_argument('--connect_options', help='options to connect (M)', action='append')
    parser.add_argument('--listen_options', help='options to listen (M)', action='append')
    parser.add_argument('--config', type=argparse.FileType(encoding='utf-8'), help='path to configuration file')
    parser.add_argument('--loglevel', type=str.lower, choices=['error', 'warning', 'info', 'debug'], help='logging level (defaults to info)')
    parser.add_argument('--libofp', help='argument to pass to libofp (M)', action='append')
    parser.add_argument('--ofversion', type=int, help='openflow version (M)', action='append')
    group = parser.add_argument_group('ssl settings')
    group.add_argument('--cert', type=argparse.FileType(encoding='ascii'), help='path to ssl certificate with its associated private key (PEM format)')
    group.add_argument('--cafile', type=argparse.FileType(encoding='ascii'), help='path to ssl certificate for authority/verification (PEM format)')
    group.add_argument('--password', help='password to ssl private key, if necessary')
    parser.add_argument('remainder', nargs=argparse.REMAINDER)
    return parser


def _logging_config(config):
    """
    Construct and return our logging configuration dictionary.
    """
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'complete': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'complete'
            }
        },
        'loggers': {
            'pylibofp': {
                'level': config.loglevel.upper()
            },
            'pylibofp.app': {
                'level': config.loglevel.upper()
            },
            'asyncio': {
                'level': 'WARNING'      # avoid polling msgs at 'INFO' level
            }
        },
        'root': {
            'handlers': ['console']
        }
    }


def _check_invariant(config):
    """
    Verify the config object is set up correctly.
    """
    for key in _DEFAULT_VALUES:
        if type(_DEFAULT_VALUES[key]) != type(config[key]):
            raise ValueError('Unexpected type for config key: %s' % key)


def _yaml_load(stream, object_hook=None):
    """
    Load YAML from stream (safely). Convert mappings to use the specified object_hook.

    Adapted from:
    http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
    """
    import yaml
    class ObjectLoader(yaml.SafeLoader):
        pass
    def construct_mapping(loader, node):
        return object_hook(loader.construct_mapping(node))
    ObjectLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    result = yaml.load(stream, ObjectLoader)
    if not result:
        raise ValueError('Expecting value')
    assert isinstance(result, object_hook)
    return result

