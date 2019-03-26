"""Simple API for async web server and web client."""

import asyncio
import re
import aiohttp
from aiohttp import web

# Query string variable may end with [].
_VAR_REGEX = re.compile(r'^\{(\w+(?:\[\])?)\}$')
_LOG_FORMAT = '%a "%r" %s %b "%{Referrer}i" "%{User-Agent}i"'

ClientResponseError = aiohttp.ClientResponseError  # type: ignore

_get_running_loop = getattr(asyncio, 'get_running_loop', asyncio.get_event_loop)


class HttpServer:
    """Simple async web server.

    Usage:

        web = HttpServer(('', 8000))

        @web.get('/foo')
        async def get_foo():
            return 'foo'

        @web.get('/foo/{arg}/foo.json', 'json')
        async def get_foo_json(arg):
            return { 'foo': arg }

        await web.start()
        ...
        await web.stop()

    Alternatively, you can create the HttpServer() instance, then run it
    in a new task. Cancel the task to stop the server.

        task = asyncio.create_task(web.serve_forever())
        ...
        task.cancel()
    """

    def __init__(self, endpoint=None, logger=None):
        """Initialize web server.

        Args:
            endpoint (tuple): host, port pair
            logger (Logger): optional logger
        """
        self.endpoint = endpoint
        self.logger = logger
        self._app = web.Application()
        self._runner = None
        self._site = None

    async def start(self):
        """Start web server listening on endpoint."""
        assert self._site is None
        assert len(self.endpoint) == 2

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.endpoint[0],
                                 self.endpoint[1])
        await self._site.start()

        if self.logger:
            self.logger.info('HttpServer: Start listening on %s',
                             self.endpoint)

    async def stop(self):
        """Stop web server."""
        if self._site is None:
            return

        await self._runner.cleanup()

        if self.logger:
            self.logger.info('HttpServer: Stop listening on %s', self.endpoint)

    async def serve_forever(self):
        """Start the web server and run until task is cancelled."""
        try:
            serve_future = _get_running_loop().create_future()
            await self.start()
            await serve_future
        except asyncio.CancelledError:
            await self.stop()

    def get(self, path, payload_type='text'):
        """Decorate HTTP GET requests."""
        route_path, route_vars = _split_route(path)
        route_get = _ROUTE_GET[payload_type]

        def _wrap(func):
            assert func is not None
            get = route_get(route_vars, func)
            self._app.router.add_get(route_path, get)
            return func

        return _wrap

    def post(self, path, payload_type):
        """Decorate HTTP POST requests."""
        route_path, route_vars = _split_route(path)
        route_post = _ROUTE_POST[payload_type]

        def _wrap(func):
            assert func is not None
            post = route_post(route_vars, func)
            self._app.router.add_post(route_path, post)
            return func

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
        match = _VAR_REGEX.match(name)
        if not match:
            raise ValueError("Invalid variable name: %s" % name)
        route_vars.append(match.group(1))
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
        post_data = await request.json()
        kwds = _build_kwds(request, route_vars, post_data)
        return await _respond_json(func, kwds)

    return _post


def _route_post_text(route_vars, func):
    async def _post(request):
        post_data = await request.text()
        kwds = _build_kwds(request, route_vars, post_data)
        return await _respond_text(func, kwds)

    return _post


_ROUTE_GET = {'json': _route_get_json, 'text': _route_get_text}

_ROUTE_POST = {'json': _route_post_json, 'text': _route_post_text}


def _build_kwds(request, route_vars, post_data=None):
    kwds = request.match_info.copy()
    for var in route_vars:
        multi, key = _is_multiple_value(var)
        if multi:
            kwds[key] = request.query.getall(var, [])
        else:
            kwds[key] = request.query.get(var)
    if post_data is not None:
        kwds['post_data'] = post_data
    return kwds


def _is_multiple_value(value):
    if value.endswith('[]'):
        return True, value[:-2]
    return False, value


async def _respond_json(func, kwds):
    if asyncio.iscoroutinefunction(func):
        result = await func(**kwds)
    else:
        result = func(**kwds)
    return web.json_response(result)


async def _respond_text(func, kwds):
    if asyncio.iscoroutinefunction(func):
        result = await func(**kwds)
    else:
        result = func(**kwds)
    # If result is a 2-tuple, treat it as (result, status)
    if isinstance(result, tuple):
        assert len(result) == 2
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
        """Initialize web client."""
        self._client = None

    async def start(self):
        """Start async web client."""
        assert self._client is None
        self._client = aiohttp.ClientSession(
            raise_for_status=True, conn_timeout=15)

    async def stop(self):
        """Stop async web client."""
        # The following line requires aiohttp 2.2.2 or later.
        await self._client.close()
        self._client = None

    async def get(self, url):
        """Fetch text contents of given url."""
        async with self._client.get(url) as response:
            return await response.text()

    async def post(self, url, *, post_data):
        """Post to url with text."""
        async with self._client.post(url, text=post_data) as response:
            return await response.text()

    async def get_json(self, url):
        """Fetch JSON contents of given url."""
        async with self._client.get(url) as response:
            return await response.json()

    async def post_json(self, url, *, post_data):
        """Post to url with JSON data."""
        async with self._client.post(url, json=post_data) as response:
            return await response.json()
