from .asynctestcase import AsyncTestCase
from zof.http import HttpServer, HttpClient, ClientResponseError

import logging
from zof.logging import init_logging

init_logging('info')


class HttpTestCase(AsyncTestCase):
    async def test_http_server(self):
        logger = logging.getLogger('zof.test_http')
        web = HttpServer(logger=logger)

        @web.get_text('/')
        @web.get_text('/abc')
        async def _get_root():
            return 'Blah\n\u1E03lah'

        @web.get_json('/test/{var1}?{var2}')
        async def _get(var1, var2):
            return {'var1': var1, 'var2': var2}

        @web.post_json('/test/{var1}?{var2}&{var3}')
        async def _post(var1, var2, var3, post_data):
            return {
                'var1': var1,
                'var2': var2,
                'var3': var3,
                'post_data': post_data
            }

        await web.start('127.0.0.1:9010')

        client = HttpClient()
        await client.start()

        data = await client.get_text('http://127.0.0.1:9010/')
        self.assertEqual(data, 'Blah\n\u1E03lah')

        data = await client.get_text('http://127.0.0.1:9010/abc')
        self.assertEqual(data, 'Blah\n\u1E03lah')

        data = await client.get_json('http://127.0.0.1:9010/test/foo?var2=bar')
        self.assertEqual(data, {'var1': 'foo', 'var2': 'bar'})

        data = await client.get_json('http://127.0.0.1:9010/test/xyz')
        self.assertEqual(data, {'var1': 'xyz', 'var2': None})

        data = await client.post_json(
            'http://127.0.0.1:9010/test/a?var2=3&var3=4', post_data={'x': 1})
        self.assertEqual(data, {
            'var1': 'a',
            'var2': '3',
            'var3': '4',
            'post_data': {
                'x': 1
            }
        })

        # "/test" fails because {var1} is required.
        with self.assertRaises(ClientResponseError):
            await client.get_json('http://127.0.0.1:9010/test')

        # "/test/a/" doesn't match because of the / at the end.
        with self.assertRaises(ClientResponseError):
            await client.post_json(
                'http://127.0.0.1:9010/test/a/', post_data={})

        await client.stop()
        await web.stop()
