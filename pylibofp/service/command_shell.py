import shlex
import inspect
import asyncio
from collections import defaultdict

from prompt_toolkit.shortcuts import prompt_async
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.contrib.completers import WordCompleter
from prompt_toolkit import AbortAction

from .. import ofp_app, ofp_run
from ..event import make_event
from ..logging import TailBufferedHandler, PatchedConsoleHandler
from ..exception import CommandException


app = ofp_app('service.command_shell')
app.foreground_task = None
app.command_prompt = '> '


_tail_handler = TailBufferedHandler.install()
_console_handler = PatchedConsoleHandler.install()


@app.event('start')
async def command_shell(_event):
    """Async task to listen for input and execute commands."""
    # The command shell task can be interrupted with CTRL-C (KeyboardInterrupt).
    app.foreground_task = asyncio.Task.current_task()
    cmds = [h.subtype.lower() for h in all_command_handlers()]
    completer = WordCompleter(cmds)
    history = InMemoryHistory()
    bold_style = style_from_dict({Token: 'bold'})
    while True:
        try:
            command = await prompt_async(
                app.command_prompt,
                history=history,
                completer=completer,
                style=bold_style,
                patch_stdout=True,
                complete_while_typing=False,
                on_abort=AbortAction.RETRY)
            if command:
                await run_command(command)
        except EOFError:
            app.post_event('EXIT')
            break
    app.foreground_task = None


@app.event('signal', signal='SIGINT')
def handle_sigint(event):
    """Cancel async command_shell task."""
    if app.foreground_task:
        app.foreground_task.cancel()
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
                app.logger.exception(ex)
        except asyncio.CancelledError:
            app.logger.debug('CancelledError')
        except Exception as ex:  # pylint: disable=broad-except
            app.logger.exception(ex)



def exec_command(cmd, handler):
    parser = handler.options.get('argparser')
    if parser:
        assert isinstance(parser, app.command.ArgumentParser)
        # Make sure `prog` is set to correct command name.
        parser.prog = cmd[0]
        cmd = parser.parse_args(cmd[1:])
    event = make_event(event='COMMAND', args=cmd)
    return handler(event, app)


def find_command_handler(cmd):
    for handler in all_command_handlers():
        if handler.subtype == cmd.upper():
            return handler
    return None


def all_command_handlers():
    result = []
    for capp in app.all_apps():
        if 'command' in capp.handlers:
            result += capp.handlers['command']
    return result


#=================#
# C O M M A N D S #
#=================#


def _help_args():
    desc = '''List all commands or show help for a specific command.
    '''
    parser = app.command.ArgumentParser(desc)
    parser.add_argument('command', nargs='?', help='name of command')
    return parser


@app.command('help', argparser=_help_args())
def help_cmd(event):
    """List all commands or show help for a specific command."""
    cmd_name = event.args.command
    if cmd_name:
        yield _show_help(cmd_name)
    else:
        for handler in all_command_handlers():
            yield '%-12s - %s' % (handler.subtype.lower(), handler.help_brief())


def _show_help(cmd_name):
    handler = find_command_handler(cmd_name)
    if not handler:
        return '%s: command not found' % cmd_name
    parser = handler.options.get('argparser')
    if parser:
        parser.prog = cmd_name
        return parser.format_help()
    else:
        return handler.help()


def _ls_args():
    parser = app.command.ArgumentParser()
    parser.add_argument('-l', '--long', action='store_true', help='list in long format')
    return parser


@app.command('ls', argparser=_ls_args())
def ls_cmd(event):
    """(TODO in device service) List datapaths, ports, or flows."""
    print(event)


def _ps_args():
    desc = '''List all running apps/tasks.

    Columns:
      PREC  app precedence value (empty for tasks)
      NAME  app name
    '''
    parser = app.command.ArgumentParser(description=desc)
    parser.add_argument('-a', '--all', action='store_true', help='show all tasks')
    return parser


@app.command('ps', argparser=_ps_args())
def ps_cmd(event):
    """List all running apps/tasks."""
    app_tasks = defaultdict(list)
    if event.args.all:
        for task in asyncio.Task.all_tasks():
            capp = getattr(task, 'ofp_task_app', None)
            app_tasks[capp].append(task)

    yield 'PREC NAME'
    for capp in app.all_apps():
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
    parser = app.command.ArgumentParser(description=desc)
    parser.add_argument('-f', action='store_true', help='continue logging')
    return parser


@app.command('log', argparser=_log_args())
async def log_cmd(event):
    """Show recent log messages."""
    if event.args.f:
        _console_handler.write('Type CTRL-C to stop logging.')
    # Print out lines from tail buffer.
    for line in _tail_handler.lines():
        _console_handler.write(line)
    if event.args.f:
        # Temporarily change console log handler's level to use the root log level.
        console_level = _console_handler.level
        _console_handler.setLevel('NOTSET')
        try:
            # Wait for cancellation.
            while True:
                await asyncio.sleep(60)
        finally:
            # Change console log handler's level back.
            _console_handler.setLevel(console_level)


@app.command('exit')
def exit_cmd(_event):
    """Exit command shell."""
    app.post_event('EXIT')


if __name__ == '__main__':
    ofp_run()
