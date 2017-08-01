import asyncio
import re
import aiohttp
import aiohttp.web as web
from .objectview import to_json, from_json
from .endpoint import Endpoint

_VAR_REGEX = re.compile(r'^\{(\w+)\}$')
_LOG_FORMAT = '%a "%r" %s %b "%{Referrer}i" "%{User-Agent}i"'

ClientResponseError = aiohttp.ClientResponseError


class HttpServer:
    """Simple async web server.
    """

    def __init__(self, *, logger=None):
        self.endpoint = None
        self.logger = logger
        self.web_app = web.Application()
        self.web_handler = None
        self.web_server = None

    async def start(self, endpoint):
        self.endpoint = Endpoint(endpoint)
        loop = asyncio.get_event_loop()
        self.web_handler = self.web_app.make_handler(
            loop=loop, access_log=self.logger, access_log_format=_LOG_FORMAT)
        await self.web_app.startup()

        self.web_server = await loop.create_server(
            self.web_handler, self.endpoint.host, self.endpoint.port)

        if self.logger:
            self.logger.info('HttpServer: Start listening on %s',
                             self.endpoint)

    async def stop(self):
        self.web_server.close()
        await self.web_server.wait_closed()

        await self.web_app.shutdown()
        await self.web_handler.shutdown(timeout=10)
        await self.web_app.cleanup()

        if self.logger:
            self.logger.info('HttpServer: Stop listening on %s', self.endpoint)

    def get_json(self, path):
        route_path, route_vars = _split_route(path)

        def _wrap(func):
            get = _route_get_json(route_vars, func)
            self.web_app.router.add_get(route_path, get)

        return _wrap

    def post_json(self, path):
        route_path, route_vars = _split_route(path)

        def _wrap(func):
            post = _route_post_json(route_vars, func)
            self.web_app.router.add_post(route_path, post)

        return _wrap

    def get_text(self, path):
        route_path, route_vars = _split_route(path)

        def _wrap(func):
            get = _route_get_text(route_vars, func)
            self.web_app.router.add_get(route_path, get)
            return func

        return _wrap

    def post_text(self, path):
        route_path = route_vars = _split_route(path)

        def _wrap(func):
            post = _route_post_text(route_vars, func)
            self.web_app.router.add_post(route_path, post)

        return _wrap


def _split_route(path):
    """Split path on '?' into route_path and route_vars.

    For example, given "/path/{foo}?{bar}", return ('/path/{foo}', ['bar'])
    """
    if '?' not in path:
        return path, []
    route_path, rest = path.split('?', maxsplit=1)
    route_vars = []
    for name in rest.split('&'):
        m = _VAR_REGEX.match(name)
        if not m:
            raise ValueError("Invalid variable name: %s" % name)
        route_vars.append(m.group(1))
    return route_path, route_vars


def _route_get_json(route_vars, func):
    async def _get(request):
        kwds = _build_kwds(request, route_vars)
        return await _respond_json(func, kwds)

    return _get


def _route_get_text(route_vars, func):
    async def _get(request):
        kwds = _build_kwds(request, route_vars)
        return await _respond_text(func, kwds)

    return _get


def _route_post_json(route_vars, func):
    async def _post(request):
        post_data = await request.json(loads=from_json)
        kwds = _build_kwds(request, route_vars, post_data)
        return await _respond_json(func, kwds)

    return _post


def _route_post_text(route_vars, func):
    async def _post(request):
        post_data = await request.text()
        kwds = _build_kwds(request, route_vars, post_data)
        return await _respond_text(func, kwds)

    return _post


def _build_kwds(request, route_vars, post_data=None):
    kwds = request.match_info.copy()
    for var in route_vars:
        kwds[var] = request.query.get(var)
    if post_data is not None:
        kwds['post_data'] = post_data
    return kwds


async def _respond_json(func, kwds):
    if asyncio.iscoroutinefunction(func):
        result = await func(**kwds)
    else:
        result = func(**kwds)
    return web.json_response(result, dumps=to_json)


async def _respond_text(func, kwds):
    if asyncio.iscoroutinefunction(func):
        result = await func(**kwds)
    else:
        result = func(**kwds)
    # If result is a 2-tuple, treat it as (result, status)
    if isinstance(result, tuple):
        result, status = result
    else:
        status = 200
    if isinstance(result, bytes):
        return web.Response(
            body=result, status=status, content_type='text/plain')
    return web.Response(text=result, status=status)


class HttpClient:
    """Simple async web client.

    Usage:
        client = HttpClient()
        await client.start()

        result = await client.get_json('http://google.com')
        print(result)

        await client.stop()


    """

    def __init__(self):
        self._client = None

    async def start(self):
        assert self._client is None
        self._client = aiohttp.ClientSession(
            raise_for_status=True, json_serialize=to_json, conn_timeout=15)

    async def stop(self):
        # The following line requires aiohttp 2.2.2 or later.
        await self._client.close()
        self._client = None

    async def get_json(self, url):
        async with self._client.get(url) as response:
            return await response.json(loads=from_json)

    async def post_json(self, url, *, post_data):
        async with self._client.post(url, json=post_data) as response:
            return await response.json(loads=from_json)

    async def get_text(self, url):
        async with self._client.get(url) as response:
            return await response.text()

    async def post_text(self, url, *, post_data):
        async with self._client.post(url, text=post_data) as response:
            return await response.text()
