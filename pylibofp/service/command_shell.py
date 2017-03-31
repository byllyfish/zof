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


example_style = style_from_dict({
    # User input.
    Token: 'bold'
})

ofp = ofp_app('service.command_shell')
ofp.foreground_task = None
ofp.command_prompt = '> '


_tail_handler = TailBufferedHandler.install()
_console_handler = PatchedConsoleHandler.install()

# def command(cmd, *, help):
#     def _wrap(func):
#         options = dict(help=help)
#         ofp.subscribe(func, 'command', cmd, options)
#     return _wrap


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
        print('Unknown command "%s"' % cmd[0])
    else:
        try:
            event = make_event(event='COMMAND', command=cmd[0], args=cmd[1:])
            result = handler(event, ofp)
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
        except asyncio.CancelledError:
            ofp.logger.debug('CancelledError')
        except Exception as ex:  # pylint: disable=broad-except
            ofp.logger.exception(ex)


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


@ofp.command('help')
def help_cmd(_event):
    for handler in all_command_handlers():
        yield '%-12s - %s' % (handler.subtype.lower(), handler.help_brief())


@ofp.command('ps')
def ps_cmd(_event):
    yield 'ID PREC NAME                          MSG  EVT TASK/DONE   SND  REQ'
    all_tasks = ofp.controller.tasks()

    for app in ofp.controller.apps:
        msgs = '-'
        if 'message' in app.handlers:
            msgs = sum(h.count for h in app.handlers['message'])

        evts = '-'
        if 'event' in app.handlers:
            evts = sum(h.count for h in app.handlers['event'])

        tasks = 0
        for task in all_tasks:
            if task.ofp_task_app == app:
                tasks += 1

        done = app.counters['done']
        send = app.counters['send']
        req = app.counters['request']

        yield '%2d %4d %-28s %4s %4s %4s/%-4s  %4s %4s' % (
            app.id, app.precedence, app.name, msgs, evts, tasks, done, send,
            req)


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
    ofp.post_event('EXIT')


if __name__ == '__main__':
    ofp_run()
