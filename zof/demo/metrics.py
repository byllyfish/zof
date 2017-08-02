import argparse
import zof
from zof import exception as _exc
from zof.http import HttpServer
import zof.service.device as dev
from prometheus_client import REGISTRY, CollectorRegistry, generate_latest, ProcessCollector
from prometheus_client.core import CounterMetricFamily


def arg_parser():
    parser = argparse.ArgumentParser(prog='Metrics', description='Metric Demo')
    parser.add_argument(
        '--metrics-endpoint', help='HTTP endpoint for metrics server')
    return parser


app = zof.Application('metrics', arg_parser=arg_parser())
web = HttpServer()


@app.event('preflight')
def preflight(_):
    if not app.args.metrics_endpoint:
        # If we're not listening, unload the application.
        raise _exc.PreflightUnloadException()


@app.event('start')
async def start(_):
    # Start a process collector for our oftr subprocess.
    ProcessCollector(namespace='oftr', pid=lambda: app.oftr_connection.pid)
    await web.start(app.args.metrics_endpoint)
    app.logger.info('Start listening on %s', app.args.metrics_endpoint)


@app.event('stop')
async def stop(_):
    await web.stop()
    app.logger.info('Stop listening on %s', app.args.metrics_endpoint)


@web.get_text('/')
@web.get_text('/metrics')
@web.get_text('/metrics/')
async def metrics():
    return generate_latest(REGISTRY)


@web.get_text('/metrics/ports?{target}')
async def ports(target):
    if target:
        met = PortMetrics()
        await _collect_port_stats(target, met)
    else:
        # FIXME(bfish): Collecting stats from multiple datapaths serially is
        # problematic. A slow responder could hold up collection. If we allow
        # parallelism, we must enforce a strict timeout to limit the scrape
        # duration. The advantage of collecting them all is that we don't
        # have to worry about service discovery.
        met = PortMetrics(include_instance=True)
        for device in dev.get_devices():
            await _collect_port_stats(device.datapath_id, met)
    return _dump_prometheus(met.metrics())


PORT_STATS = zof.compile('''
type: REQUEST.PORT_STATS
msg:
  port_no: ANY
''')


def _supported_counter(value):
    return value != 0xffffffffffffffff


class PortMetrics:
    def __init__(self, include_instance=False):
        self.include_instance = include_instance
        if include_instance:
            labels = ['port_no', 'instance']
        else:
            labels = ['port_no']
        self.tx_bytes = CounterMetricFamily('port_tx_bytes_total',
                                            'bytes transmitted', None, labels)
        self.rx_bytes = CounterMetricFamily('port_rx_bytes_total',
                                            'bytes received', None, labels)
        self.tx_packets = CounterMetricFamily(
            'port_tx_packets_total', 'packets transmitted', None, labels)
        self.rx_packets = CounterMetricFamily('port_rx_packets_total',
                                              'packets received', None, labels)
        self.tx_dropped = CounterMetricFamily(
            'port_tx_dropped_total', 'packets dropped by TX', None, labels)
        self.rx_dropped = CounterMetricFamily(
            'port_rx_dropped_total', 'packets dropped by RX', None, labels)
        self.rx_errors = CounterMetricFamily('port_rx_errors_total',
                                             'receive errors', None, labels)
        self.duration = CounterMetricFamily(
            'port_duration_seconds_total', 'duration in seconds', None, labels)
        # TODO(bfish): self.up = GaugeMetricFamily()

    def metrics(self):
        return [
            self.tx_bytes, self.rx_bytes, self.tx_packets, self.rx_packets,
            self.tx_dropped, self.rx_dropped, self.rx_errors, self.duration
        ]

    def update(self, dpid, stat):
        if self.include_instance:
            labels = [str(stat.port_no), dpid]
        else:
            labels = [str(stat.port_no)]
        for counter, value in [(self.tx_bytes, stat.tx_bytes),
                               (self.rx_bytes, stat.rx_bytes),
                               (self.tx_packets, stat.tx_packets),
                               (self.rx_packets, stat.rx_packets),
                               (self.tx_dropped, stat.tx_dropped),
                               (self.rx_dropped, stat.rx_dropped),
                               (self.rx_errors, stat.rx_errors)]:
            if _supported_counter(value):
                counter.add_metric(labels, value)
        if stat.duration != '0':
            self.duration.add_metric(labels, float(stat.duration))


async def _collect_port_stats(dpid, metric):
    try:
        reply = await PORT_STATS.request(datapath_id=dpid)
    except _exc.ControllerException as ex:
        app.logger.warning('Unable to retrieve stats: %r', ex)
        return

    for stat in reply.msg:
        metric.update(dpid, stat)


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
    zof.run()
