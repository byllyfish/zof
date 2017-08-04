import re
import os
import difflib
from glob import glob
from zof.connection import Connection
from .asynctestcase import AsyncTestCase

_UPDATE_GOLDEN = False

HERE = os.path.abspath(os.path.dirname(__file__))
COOKBOOK_DIR = os.path.join(HERE, '../doc/cookbook')

RECIPE = re.compile(r'(?ms)\n\[source,yaml\]\n----\n(.*?\n)----\n')

# Pass these args when launching oftr.
OFTR_ARGS = '--roundtrip --ofversion=4'


class CookbookTestCase(AsyncTestCase):
    """
    Verify that YAML code in the "cookbook" asciidoc is valid, and roundtrips to
    the expected canonical form.
    """

    async def setUp(self):
        oftr_options = {'subcmd': 'encode', 'args': OFTR_ARGS}
        self.conn = Connection(oftr_options=oftr_options)
        await self.conn.connect()

    async def tearDown(self):
        self.conn.close(write=True)
        return_code = await self.conn.disconnect()
        if return_code:
            raise Exception('oftr exited with return code %d' % return_code)

    async def test_cookbooks(self):
        for filename in glob(os.path.join(COOKBOOK_DIR, '*.adoc')):
            name = os.path.basename(filename)
            with self.subTest(name):
                await self.check_file(name)

    async def check_file(self, filename):
        result = []
        for item in _read_cookbook(filename):
            if _UPDATE_GOLDEN:
                print(item)
            self._write(item)
            result += ['---\n']
            result += _comment(item)
            result += await self._read_msg()

        golden_filename = 'cookbook-%s.yml' % filename
        if _UPDATE_GOLDEN:
            _save(result, golden_filename)
        else:
            diff = _compare(result, golden_filename)
            for line in diff:
                print(line, end='')
            self.assertFalse(diff)

    def _write(self, data):
        self.conn.write(bytes(data, 'utf-8'), delimiter=b'\n---\n')

    async def _read_msg(self):
        result = []
        while True:
            line = await self.conn.readline(b'\n')
            if not line or line == b'...':
                break
            if line == b'---' or not line.rstrip():
                continue
            result.append(line.decode('utf-8') + '\n')
        return result


def _read_cookbook(filename):
    with open(os.path.join(COOKBOOK_DIR, filename)) as input_:
        data = input_.read()

    for item in RECIPE.finditer(data):
        yield item.group(1)


def _comment(s):
    return ['# %s' % line for line in s.splitlines(keepends=True)]


def _compare(result, filename):
    with open(os.path.join(HERE, filename)) as input_:
        data = input_.readlines()

    return list(difflib.unified_diff(data, result, n=1))


def _save(result, filename):
    with open(os.path.join(HERE, filename), 'w') as output_:
        output_.writelines(result)
