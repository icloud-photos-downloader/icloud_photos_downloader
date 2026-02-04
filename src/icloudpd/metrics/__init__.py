"""Metrics collection package for iCloud Photos Downloader.

Provides Prometheus and StatsD metrics support with a unified interface.
"""

from icloudpd.metrics.collector import CompositeCollector, MetricsCollector, NoOpCollector

__all__ = [
    "MetricsCollector",
    "NoOpCollector",
    "CompositeCollector",
    "create_metrics_collector",
]


def create_metrics_collector(
    backend: str,
    prometheus_host: str = "0.0.0.0",
    prometheus_port: int = 9090,
    statsd_host: str = "localhost",
    statsd_port: int = 8125,
    statsd_prefix: str = "icloudpd",
    instance: str | None = None,
) -> MetricsCollector:
    """Factory function to create the appropriate metrics collector.

    Args:
        backend: One of 'none', 'prometheus', 'statsd', or 'both'
        prometheus_host: Host to bind Prometheus HTTP server (default: 0.0.0.0)
        prometheus_port: Port for Prometheus HTTP server (default: 9090)
        statsd_host: StatsD server host (default: localhost)
        statsd_port: StatsD server port (default: 8125)
        statsd_prefix: Prefix for StatsD metric names (default: icloudpd)
        instance: Optional instance label to add to all metrics

    Returns:
        MetricsCollector instance for the specified backend
    """
    if backend == "none":
        return NoOpCollector()

    collectors: list[MetricsCollector] = []

    if backend in ("prometheus", "both"):
        from icloudpd.metrics.prometheus_collector import PrometheusCollector

        collectors.append(PrometheusCollector(prometheus_host, prometheus_port, instance))

    if backend in ("statsd", "both"):
        from icloudpd.metrics.statsd_collector import StatsDCollector

        collectors.append(StatsDCollector(statsd_host, statsd_port, statsd_prefix, instance))

    if len(collectors) == 0:
        return NoOpCollector()
    elif len(collectors) == 1:
        return collectors[0]
    else:
        return CompositeCollector(collectors)
