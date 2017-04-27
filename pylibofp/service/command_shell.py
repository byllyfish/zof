import shlex
import inspect
import asyncio

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


example_style = style_from_dict({
    # User input.
    Token: 'bold'
})

ofp = ofp_app('service.command_shell')
ofp.foreground_task = None
ofp.command_prompt = '> '


_tail_handler = TailBufferedHandler.install()
_console_handler = PatchedConsoleHandler.install()


@ofp.event('start')
async def command_shell(_event):
    # The command shell task can be interrupted with CTRL-C (KeyboardInterrupt).
    ofp.foreground_task = asyncio.Task.current_task()
    cmds = [h.subtype.lower() for h in all_command_handlers()]
    completer = WordCompleter(cmds)
    history = InMemoryHistory()
    while True:
        try:
            command = await prompt_async(
                ofp.command_prompt,
                history=history,
                completer=completer,
                style=example_style,
                patch_stdout=True,
                complete_while_typing=False,
                on_abort=AbortAction.RETRY)
            if command:
                await run_command(command)
        except EOFError:
            ofp.post_event('EXIT')
            break
    ofp.foreground_task = None


@ofp.event('signal', signal='SIGINT')
def handle_sigint(event):
    if ofp.foreground_task:
        ofp.foreground_task.cancel()
        event.exit = False


async def run_command(command):
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
                ofp.logger.exception(ex)
        except asyncio.CancelledError:
            ofp.logger.debug('CancelledError')
        except Exception as ex:  # pylint: disable=broad-except
            ofp.logger.exception(ex)



def exec_command(cmd, handler):
    parser = handler.options.get('argparser')
    if parser:
        assert isinstance(parser, ofp.command.ArgumentParser)
        # Make sure `prog` is set to correct command name.
        parser.prog = cmd[0]
        cmd = parser.parse_args(cmd[1:])
    event = make_event(event='COMMAND', args=cmd)
    return handler(event, ofp)


def find_command_handler(cmd):
    for handler in all_command_handlers():
        if handler.subtype == cmd.upper():
            return handler
    return None


def all_command_handlers():
    result = []
    for app in ofp.all_apps():
        if 'command' in app.handlers:
            result += app.handlers['command']
    return result

#===============================================================================
# C O M M A N D S 
#===============================================================================

def _help_args():
    parser = ofp.command.ArgumentParser()
    parser.add_argument('command', nargs='?', help='name of command')
    return parser


@ofp.command('help', argparser=_help_args())
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
    parser = ofp.command.ArgumentParser()
    parser.add_argument('-l', action='store_true', help='list in long format')
    return parser


@ofp.command('ls', argparser=_ls_args())
def ls_cmd(event):
    """(TODO in device service) List datapaths, ports, or flows."""
    print(event)
    pass

def _ps_args():
    parser = ofp.command.ArgumentParser()
    parser.add_argument('-a', help='')
    return parser


@ofp.command('ps', argparser=_ps_args())
def ps_cmd(event):
    """List all running apps/tasks."""
    print(event)
    yield 'PREC NAME'
    for app in ofp.all_apps():
        yield '%4d %s' % (app.precedence, app.name)


@ofp.command('task')
def task_cmd(_event):
    yield 'ID  NAME   SCOPE   APP   AWAIT RUNNING'
    for task in ofp.controller.tasks():
        coro = task._coro
        yield '%s %s %s %r %s' % (coro.__qualname__, task.ofp_task_scope,
                                  task.ofp_task_app.name, coro.cr_await,
                                  coro.cr_running)
    yield 'Other tasks'
    for task in asyncio.Task.all_tasks():
        yield '%r' % task._coro


@ofp.command('log')
async def log_cmd(_event):
    # Print out lines from tail buffer.
    for line in _tail_handler.lines():
        _console_handler.write(line)
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


@ofp.command('net')
async def net_cmd(_event):
    result = await ofp.rpc_call('OFP.LIST_CONNECTIONS', conn_id=0)
    for conn in result.stats:
        print(conn)


@ofp.command('close')
async def close_cmd(event):
    result = await ofp.rpc_call('OFP.CLOSE', conn_id=int(event.args[0]))
    print(result)


@ofp.command('exit')
def exit_cmd(_event):
    """Exit command shell."""
    ofp.post_event('EXIT')


if __name__ == '__main__':
    ofp_run()
