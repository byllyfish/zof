import argparse
import ofp_app
from ofp_app import exception as _exc
from ofp_app.http import HttpServer
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest, ProcessCollector
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
import time


def arg_parser():
    parser = argparse.ArgumentParser(prog='Metrics', description='Metric Demo')
    parser.add_argument(
        '--metric-endpoint', help='HTTP endpoint for metric server')
    return parser


app = ofp_app.Application('metrics', arg_parser=arg_parser())
web = HttpServer(logger=app.logger)


@app.event('preflight')
def preflight(_):
    if not app.args.metric_endpoint:
        # If we're not listening, unload the application.
        raise _exc.PreflightUnloadException()


@app.event('start')
async def start(_):
    # Start a process collector for our oftr subprocess.
    ProcessCollector(namespace='oftr', pid=app.oftr_connection.pid)
    if app.args.metric_endpoint:
        await web.start(app.args.metric_endpoint)


@app.event('stop')
async def stop(_):
    await web.stop()


@web.get_text('/')
@web.get_text('/metrics')
@web.get_text('/metrics/')
async def metrics():
    return generate_latest(REGISTRY)


@web.get_text('/metrics/ports?{target}')
async def ports(target):
    try:
        stats = await _collect_port_stats(target)
    except _exc.DeliveryException as ex:
        return 'ERROR: %s' % str(ex)
    return _dump_prometheus(stats)


PORT_STATS = ofp_app.compile('''
type: REQUEST.PORT_STATS
msg:
  port_no: ANY
''')

async def _collect_port_stats(target):
    scrape_start = time.time()
    tag_names = ['port']
    tx_bytes = CounterMetricFamily('port_tx_bytes', 'bytes transmitted', None, tag_names)
    rx_bytes = CounterMetricFamily('port_rx_bytes', 'bytes received', None, tag_names)

    reply = await PORT_STATS.request(datapath_id=target)
    for stat in reply.msg:
        tags = [str(stat.port_no)]
        tx_bytes.add_metric(tags, stat.tx_bytes)
        rx_bytes.add_metric(tags, stat.rx_bytes)

    scrape_duration = GaugeMetricFamily('scrape_duration_seconds', 'Time this scrape took, in seconds', time.time() - scrape_start)
    return [tx_bytes, rx_bytes, scrape_duration]


class _MyCollector:
    def __init__(self, stats):
        self.stats = stats
    def collect(self):
        return self.stats


def _dump_prometheus(stats):
    registry = CollectorRegistry()
    registry.register(_MyCollector(stats))
    return generate_latest(registry)


if __name__ == '__main__':
    ofp_app.run()
