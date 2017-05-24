import asyncio
import aiohttp.web as web
import inspect
from pylibofp.objectview import to_json

class HttpServer(object):
    """Simple async web server.
    """

    def __init__(self, endpoint, *, logger):
        self.endpoint = _parse_endpoint(endpoint)
        self.logger = logger
        self.web_app = web.Application()
        self.web_handler = None
        self.web_server = None

    async def start(self):
        loop = asyncio.get_event_loop()
        self.web_handler = self.web_app.make_handler(loop=loop, access_log=self.logger)
        await self.web_app.startup()

        self.web_server = await loop.create_server(self.web_handler, self.endpoint[0], self.endpoint[1])
        self.logger.info('HttpServer: Start listening on %s:%s' % self.endpoint)

    async def stop(self):
        self.web_server.close()
        await self.web_server.wait_closed()

        await self.web_app.shutdown()
        await self.web_handler.shutdown(timeout=10)
        await self.web_app.cleanup()
        self.logger.info('HttpServer: Stop listening on %s:%s' % self.endpoint)


    def route(self, path):
        def _wrap(func):
            async def _exec_async(req):
                return web.json_response(await func(**req.match_info), dumps=to_json)
            def _exec_sync(req):
                return web.json_response(func(**req.match_info), dumps=to_json)
            _exec = _exec_async if inspect.iscoroutinefunction(func) else _exec_sync
            self.web_app.router.add_get(path, _exec)
            return func
        return _wrap

def _parse_endpoint(endpoint):
    return ('127.0.0.1', 8080)
