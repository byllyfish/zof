import unittest
import asyncio
from zof.callbackinfo import CallbackInfo


class CallbackInfoTestCase(unittest.TestCase):

    def test_inspect_decorated(self):
        items = [_tuple(item) for item in DECORATED]
        expected = [
            ('fa(a)', 1, None, False, False), 
            ('fb(a, b=3)', 1, None, False, False), 
            ('afa(a)', 1, None, False, False), 
            ('afb(a, b=3)', 1, None, False, False), 
            ('local_func.<locals>.fc(a)', 1, None, False, False), 
            ('local_func.<locals>.Foo.fd(self, a)', 1, 'Foo', True, False), 
            ('Foo.fe(self, a)', 1, 'Foo', True, False), 
            ('Foo.ff(a, b=1)', 1, 'Foo', False, False), 
            ('Foo.fg(a)', 1, 'Foo', False, False), 
            ('Foo.fh(cls, a)', 1, 'Foo', False, True), 
            ('Foo.afe(self, a)', 1, 'Foo', True, False), 
            ('Foo.aff(a, b=1)', 1, 'Foo', False, False), 
            ('Foo.afg(a)', 1, 'Foo', False, False), 
            ('Foo.afh(cls, a)', 1, 'Foo', False, True)
        ]
        self.assertEqual(items, expected)

    def test_inspect_direct(self):
        items = [_tuple(CallbackInfo(func)) for func in DIRECT]
        expected = [
            ('fa(a)', 1, None, False, False), 
            ('fb(a, b=3)', 1, None, False, False), 
            ('afa(a)', 1, None, False, False), 
            ('afb(a, b=3)', 1, None, False, False), 
            ('Foo.fe(self, a)', 1, 'Foo', True, False), 
            ('Foo.ff(a, b=1)', 1, 'Foo', False, False), 
            ('Foo.fg(a)', 1, 'Foo', False, False), 
            ('Foo.fh(a)', 1, 'Foo', False, False),
            ('Foo.afe(self, a)', 1, 'Foo', True, False), 
            ('Foo.aff(a, b=1)', 1, 'Foo', False, False), 
            ('Foo.afg(a)', 1, 'Foo', False, False), 
            ('Foo.afh(a)', 1, 'Foo', False, False)
        ]
        self.assertEqual(items, expected)

    def test_bind_decorated(self):
        instance = Foo()
        results = [_bindcall1(item, instance) for item in DECORATED]
        expected = ['fa', 'fb', 'afa', 'afb', 'fc', 'fd', 'fe', 'ff', 'fg', 'fh', 'afe', 'aff', 'afg', 'afh']
        self.assertEqual(results, expected)

    def test_bind_direct(self):
        items = [CallbackInfo(func) for func in DIRECT]
        instance = Foo()
        results = [_bindcall1(item, instance) for item in items]
        expected = ['fa', 'fb', 'afa', 'afb', 'fe', 'ff', 'fg', 'fh', 'afe', 'aff', 'afg', 'afh']
        self.assertEqual(results, expected)



def _tuple(info):
    return (info.name, info.args_required, info.class_, info.instance_required, info.class_required)

def _bindcall1(info, obj):
    func = info.bind(obj)
    if asyncio.iscoroutinefunction(func):
        return _run(func(1))
    return func(1)

def _run(coro):
    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(coro)
    loop.close()
    return result


DECORATED = []

def inspectx(func):
    DECORATED.append(CallbackInfo(func))
    return func


# Test functions.

@inspectx
def fa(a):
    return 'fa'

@inspectx
def fb(a, b=3):
    return 'fb'

@inspectx
async def afa(a):
    return 'afa'

@inspectx
async def afb(a, b=3):
    return 'afb'

# Test locally defined functions.

def local_func():
    @inspectx
    def fc(a):
        return 'fc'

    class Foo:
        @inspectx
        def fd(self, a):
            return 'fd'

local_func()

# Test class methods.

class Foo:
    # Single arg method
    @inspectx
    def fe(self, a):
        return 'fe'

    # Single arg method, with default arg
    @inspectx
    def ff(a, b=1):
        return 'ff'

    # Static method
    @inspectx
    @staticmethod
    def fg(a):
        return 'fg'

    # Class method
    @inspectx
    @classmethod
    def fh(cls, a):
        return 'fh'

    # Single arg method (async)
    @inspectx
    async def afe(self, a):
        return 'afe'

    # Single arg method, with default arg (async)
    @inspectx
    async def aff(a, b=1):
        return 'aff'

    # Static method (async)
    @inspectx
    @staticmethod
    async def afg(a):
        return 'afg'

    # Class method (async)
    @inspectx
    @classmethod
    async def afh(cls, a):
        return 'afh'


DIRECT = (fa, fb, afa, afb, Foo.fe, Foo.ff, Foo.fg, Foo.fh, Foo.afe, Foo.aff, Foo.afg, Foo.afh)
