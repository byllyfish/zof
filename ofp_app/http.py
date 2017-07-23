import asyncio
import inspect
import re
import aiohttp.web as web
from .objectview import to_json, from_json

MIMETYPE_JSON = 'application/json'
MIMETYPE_TEXT = 'text/plain'


class HttpServer(object):
    """Simple async web server.
    """

    def __init__(self, *, logger):
        self.endpoint = None
        self.logger = logger
        self.web_app = web.Application()
        self.web_handler = None
        self.web_server = None

    async def start(self, endpoint):
        self.endpoint = _parse_endpoint(endpoint)
        loop = asyncio.get_event_loop()
        self.web_handler = self.web_app.make_handler(
            loop=loop, access_log=self.logger)
        await self.web_app.startup()

        self.web_server = await loop.create_server(
            self.web_handler, self.endpoint[0], self.endpoint[1])
        self.logger.info('HttpServer: Start listening on %s',
                         endpoint_str(self.endpoint))

    async def stop(self):
        if not self.endpoint:
            return
        self.web_server.close()
        await self.web_server.wait_closed()

        await self.web_app.shutdown()
        await self.web_handler.shutdown(timeout=10)
        await self.web_app.cleanup()
        self.logger.info('HttpServer: Stop listening on %s',
                         endpoint_str(self.endpoint))

    def route(self, path, *, method='GET', content_type=MIMETYPE_JSON):
        method = method.upper()

        def _wrap(func):
            if method == 'GET':

                async def _exec_async(req):
                    return web.json_response(
                        await func(**req.match_info), dumps=to_json)

                def _exec_sync(req):
                    return web.json_response(
                        func(**req.match_info), dumps=to_json)

                _exec_get = _exec_async if inspect.iscoroutinefunction(
                    func) else _exec_sync
                self.web_app.router.add_get(path, _exec_get)
            elif method == 'POST':

                async def _exec_post(req):
                    post_data = await req.json(loads=from_json)
                    return web.json_response(
                        await func(post_data), dumps=to_json)

                self.web_app.router.add_post(path, _exec_post)
            return func

        return _wrap


_ENDPOINT_REGEX = re.compile(r'^(?:\[(.*)\]|(.*)):(\d+)$')


def _parse_endpoint(endpoint):
    if ':' not in endpoint:
        return ('', int(endpoint))
    m = _ENDPOINT_REGEX.match(endpoint)
    if not m:
        raise ValueError('Invalid endpoint: %s' % endpoint)
    return (m.group(1) or m.group(2), int(m.group(3)))


def endpoint_str(endpoint):
    if ':' in endpoint[0]:
        return '[%s]:%u' % endpoint
    return '%s:%u' % endpoint
