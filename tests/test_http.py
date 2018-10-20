import pytest
import logging

from zof.http import HttpServer, HttpClient, ClientResponseError


@pytest.mark.asyncio
async def test_http_server():
    logger = logging.getLogger('zof.test_http')
    web = HttpServer(logger=logger)

    @web.get('/', 'text')
    @web.get('/abc', 'text')
    async def _get_root():
        return 'Blah\n\u1E03lah'

    @web.get('/test/text', 'text')
    async def _get_text():
        return 'test text1'

    @web.get('/test/{var1}?{var2}', 'json')
    @web.get('/test1/{var1}?{var2[]}', 'json')
    async def _get(var1, var2):
        return {'var1': var1, 'var2': var2}

    @web.post('/test/{var1}?{var2}&{var3}', 'json')
    async def _post(var1, var2, var3, post_data):
        return {
            'var1': var1,
            'var2': var2,
            'var3': var3,
            'post_data': post_data
        }

    await web.start(('127.0.0.1', 9010))

    client = HttpClient()
    await client.start()

    data = await client.get('http://127.0.0.1:9010/')
    assert data == 'Blah\n\u1E03lah'

    data = await client.get('http://127.0.0.1:9010/abc')
    assert data == 'Blah\n\u1E03lah'

    data = await client.get_json('http://127.0.0.1:9010/test/foo?var2=bar')
    assert data == {'var1': 'foo', 'var2': 'bar'}

    data = await client.get_json('http://127.0.0.1:9010/test1/foo?var2[]=bar&var2[]=boo')
    assert data == {'var1': 'foo', 'var2': ['bar', 'boo']}

    data = await client.get_json('http://127.0.0.1:9010/test1/foo')
    assert data == {'var1': 'foo', 'var2': []}

    data = await client.get_json('http://127.0.0.1:9010/test/xyz')
    assert data == {'var1': 'xyz', 'var2': None}

    data = await client.post_json(
        'http://127.0.0.1:9010/test/a?var2=3&var3=4', post_data={
            'x': 1
        })
    assert data == {
        'var1': 'a',
        'var2': '3',
        'var3': '4',
        'post_data': {
            'x': 1
        }
    }

    data = await client.get('http://127.0.0.1:9010/test/text')
    assert data == 'test text1'

    # "/test" fails because {var1} is required.
    with pytest.raises(ClientResponseError):
        await client.get_json('http://127.0.0.1:9010/test')

    # "/test/a/" doesn't match because of the / at the end.
    with pytest.raises(ClientResponseError):
        await client.post_json(
            'http://127.0.0.1:9010/test/a/', post_data={})

    await client.stop()
    await web.stop()
