import sys
import shlex
import inspect
import asyncio
import argparse
import logging
import collections

from prompt_toolkit.shortcuts import prompt_async
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit import AbortAction

import zof
from ..event import make_event
from ..exception import ControlFlowException
from ..logging import DEFAULT_FORMATTER, STDERR_HANDLER


class CommandException(ControlFlowException):
    """Exception class used by app commands to exit.

    This exception is caught by the command_shell service.
    """

    def __init__(self, *, status, message=None):
        super().__init__()
        self.status = status
        self.message = message

    def __str__(self):
        return '[CommandException status=%s, message=%s]' % (self.status,
                                                             self.message)


class _ArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if asyncio.Task.current_task():
            raise CommandException(status=0)
        super().exit(status, message)


APP = zof.Application('command_shell')
APP.foreground_task = None
APP.command_prompt = '> '
APP.commands = {}

_Handler = collections.namedtuple('_Handler', 'subtype func options')


def _command(subtype, **kwds):
    """Command decorator.
    """

    def _wrap(func):
        upper_type = subtype.upper()
        APP.commands[upper_type] = _Handler(upper_type, func, kwds)

    return _wrap


APP.command = _command
APP.command.ArgumentParser = _ArgumentParser


@APP.event('start')
async def command_shell(_event):
    """Async task to listen for input and execute commands."""
    # The command shell task can be interrupted with CTRL-C (KeyboardInterrupt).
    APP.foreground_task = asyncio.Task.current_task()
    cmds = [h.subtype.lower() for h in all_command_handlers()]
    completer = WordCompleter(cmds)
    history = InMemoryHistory()
    bold_style = style_from_dict({Token: 'bold'})
    while True:
        try:
            command = await prompt_async(
                APP.command_prompt,
                history=history,
                completer=completer,
                style=bold_style,
                patch_stdout=True,
                complete_while_typing=False,
                on_abort=AbortAction.RETRY)
            if command:
                await run_command(command)
        except EOFError:
            zof.post_event('EXIT')
            break
    APP.foreground_task = None


@APP.event('signal', signal='SIGINT')
def handle_sigint(event):
    """Cancel async command_shell task."""
    if APP.foreground_task:
        APP.foreground_task.cancel()
        event.exit = False


async def run_command(command):
    """Run shell command."""
    cmd = shlex.split(command)
    handler = find_command_handler(cmd[0])
    if not handler:
        print('%s: command not found' % cmd[0])
    else:
        try:
            result = exec_command(cmd, handler)
            # Result of executing a handler may be:
            #  None:  handler already printed output.
            #  Iterable: we are responsible for printing output.
            #  Future: we should await the future.
            if result is None:
                return
            if inspect.isawaitable(result):
                await result
            else:
                for line in result:
                    print(line)
        except CommandException as ex:
            # Stay silent for commands that exit with status 0.
            if ex.status != 0:
                APP.logger.exception(ex)
        except asyncio.CancelledError:
            APP.logger.debug('CancelledError')
        except Exception as ex:  # pylint: disable=broad-except
            APP.logger.exception(ex)


def exec_command(cmd, handler):
    parser = handler.options.get('argparser')
    if parser:
        assert isinstance(parser, APP.command.ArgumentParser)
        # Make sure `prog` is set to correct command name.
        parser.prog = cmd[0]
        cmd = parser.parse_args(cmd[1:])
    event = make_event(event='COMMAND', args=cmd)
    return handler.func(event)


def find_command_handler(cmd):
    return APP.commands.get(cmd.upper())


def all_command_handlers():
    return list(APP.commands.values())


# =============== #
# C O M M A N D S #
# =============== #


def _help_brief(handler):
    brief = handler.options.get('brief')
    if brief:
        return brief
    parser = handler.options.get('argparser')
    if parser and parser.description:
        # Return first line of parser description.
        return parser.description.strip().split('\n', 1)[0]
    return 'No help.'


def _help_args():
    desc = '''List all commands or show help for a specific command.'''
    parser = APP.command.ArgumentParser(description=desc)
    parser.add_argument('command', nargs='?', help='name of command')
    return parser


@APP.command('help', argparser=_help_args())
def help_cmd(event):
    """List all commands or show help for a specific command."""
    cmd_name = event.args.command
    if cmd_name:
        yield _show_help(cmd_name)
    else:
        for handler in sorted(all_command_handlers()):
            yield '%-12s - %s' % (handler.subtype.lower(),
                                  _help_brief(handler))


def _show_help(cmd_name):
    handler = find_command_handler(cmd_name)
    if not handler:
        return '%s: command not found' % cmd_name
    parser = handler.options.get('argparser')
    if parser:
        parser.prog = cmd_name
        return parser.format_help()
    return ''


def _ls_args():
    parser = APP.command.ArgumentParser(
        description='List datapaths, ports or flows.')
    parser.add_argument(
        '-l', '--long', action='store_true', help='list in long format')
    return parser


@APP.command('ls', argparser=_ls_args())
def ls_cmd(event):
    """(TODO in device service) List datapaths, ports, or flows."""
    print(event)


def _ps_args():
    desc = '''List all running apps/tasks.

    Columns:
      PREC  app precedence value (empty for tasks)
      NAME  app name
    '''
    parser = APP.command.ArgumentParser(description=desc)
    parser.add_argument(
        '-a', '--all', action='store_true', help='show all tasks')
    return parser


@APP.command('ps', argparser=_ps_args())
def ps_cmd(event):
    """List all running apps/tasks."""
    app_tasks = collections.defaultdict(list)
    if event.args.all:
        for task in asyncio.Task.all_tasks():
            capp = getattr(task, 'ofp_task_app', None)
            app_tasks[capp].append(task)

    yield 'PREC NAME'
    for capp in zof.get_apps():
        yield '%4d %s' % (capp.precedence, capp.name)
        for task in app_tasks[capp]:
            yield '       %s:%s' % (_task_name(task), task.ofp_task_scope)
    for task in app_tasks[None]:
        yield '   - %s' % (_task_name(task))


def _task_name(task):
    # pylint: disable=protected-access
    return task._coro.__qualname__


def _log_args():
    desc = '''Show recent log messages.'''
    parser = APP.command.ArgumentParser(description=desc)
    parser.add_argument('-f', action='store_true', help='continue logging')
    return parser


@APP.command('log', argparser=_log_args())
async def log_cmd(event):
    """Show recent log messages."""
    if event.args.f:
        _CONSOLE_HANDLER.write('Type CTRL-C to stop logging.')
    # Print out lines from tail buffer.
    for line in _TAIL_HANDLER.lines():
        _CONSOLE_HANDLER.write(line)
    if event.args.f:
        # Temporarily change console log handler's level to use the root log level.
        console_level = _CONSOLE_HANDLER.level
        _CONSOLE_HANDLER.setLevel('NOTSET')
        try:
            # Wait for cancellation.
            while True:
                await asyncio.sleep(60)
        finally:
            # Change console log handler's level back.
            _CONSOLE_HANDLER.setLevel(console_level)


@APP.command('exit', brief='Exit command shell.')
def exit_cmd(_event):
    """Exit command shell."""
    zof.post_event('EXIT')


class TailBufferedHandler(logging.Handler):
    """Logging handler that records the last N log records."""

    def __init__(self, maxlen=10):
        super().__init__()
        self._tail = collections.deque(maxlen=maxlen)

    def lines(self):
        """Return last N log lines."""
        return self._tail

    def emit(self, record):
        """Log the specified log record."""
        try:
            self._tail.append(self.format(record))
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)

    def close(self):
        """Close the log handler."""
        super().close()
        self._tail.clear()

    @staticmethod
    def install():
        """Install tail logging handler."""
        handler = TailBufferedHandler()
        handler.setFormatter(DEFAULT_FORMATTER)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        return handler


class PatchedConsoleHandler(logging.Handler):
    """Logging handler that writes to stdout EVEN when stdout is patched.

    The normal StreamHandler grabs a reference to `sys.stdout` once at
    initialization time. This class always logs to the current sys.stdout
    which may be patched at runtime by prompt_toolkit.

    This class disables the default StreamHandler if it is logging to stderr.
    """

    def emit(self, record):
        try:
            self.write(self.format(record))
        except Exception:  # pylint: disable=broad-except
            self.handleError(record)

    def write(self, line):  # pylint: disable=no-self-use
        stream = sys.stdout
        stream.write(line)
        stream.write('\n')

    @staticmethod
    def install():
        """Install stdout logging handler.

        Change level of default stderr logging handler.
        """
        handler = PatchedConsoleHandler()
        handler.setFormatter(DEFAULT_FORMATTER)
        handler.setLevel('WARNING')
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        # From now on, only log critical events to stderr.
        STDERR_HANDLER.setLevel('CRITICAL')
        return handler


_TAIL_HANDLER = TailBufferedHandler.install()
_CONSOLE_HANDLER = PatchedConsoleHandler.install()

if __name__ == '__main__':
    zof.run()
