"""StatsD metrics collector implementation"""

import logging
from typing import Dict

from icloudpd.metrics.collector import MetricsCollector

LOGGER = logging.getLogger(__name__)


class StatsDCollector(MetricsCollector):
    """StatsD metrics collector using UDP protocol.

    Sends metrics to a StatsD server using the standard StatsD protocol.
    Uses the statsd library for UDP client functionality.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "icloudpd",
        instance: str | None = None,
    ) -> None:
        """Initialize StatsD collector.

        Args:
            host: StatsD server host (default: localhost)
            port: StatsD server port (default: 8125)
            prefix: Prefix for all metric names (default: icloudpd)
            instance: Optional instance label to add to all metrics
        """
        self._host = host
        self._port = port
        self._prefix = prefix
        self._instance = instance
        self._client = None

        try:
            import statsd

            self._client = statsd.StatsClient(host, port, prefix=prefix)
            self._statsd_available = True
            LOGGER.info(f"StatsD client configured for {host}:{port} with prefix '{prefix}'")
        except ImportError:
            LOGGER.warning(
                "statsd library not installed. StatsD metrics will be disabled. "
                "Install with: pip install statsd"
            )
            self._statsd_available = False

    def _build_metric_name(self, name: str, labels: Dict[str, str] | None) -> str:
        """Build a metric name with labels encoded as tags.

        StatsD doesn't natively support labels, so we encode them in the metric name.
        Format: metric_name.label1_value1.label2_value2

        Args:
            name: Base metric name
            labels: Optional labels to encode

        Returns:
            Metric name with encoded labels
        """
        if not labels:
            return name

        # Sort labels for consistent naming, filter out empty values
        label_parts = [f"{k}_{v}" for k, v in sorted(labels.items()) if v]
        if not label_parts:
            return name
        return f"{name}.{'.'.join(label_parts)}"

    def inc(self, name: str, value: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        if not self._statsd_available or not self._client:
            return

        merged = self._merge_labels(labels)
        metric_name = self._build_metric_name(name, merged)
        self._client.incr(metric_name, int(value))

    def set(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        if not self._statsd_available or not self._client:
            return

        merged = self._merge_labels(labels)
        metric_name = self._build_metric_name(name, merged)
        self._client.gauge(metric_name, value)

    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Record an observation using StatsD timing.

        StatsD doesn't have histograms, so we use timing metrics.
        The value is expected to be in seconds and will be converted to milliseconds.
        """
        if not self._statsd_available or not self._client:
            return

        merged = self._merge_labels(labels)
        metric_name = self._build_metric_name(name, merged)
        # StatsD timing is in milliseconds
        self._client.timing(metric_name, value * 1000)

    def start_server(self) -> None:
        """No-op for StatsD (client-side push, no server needed)."""
        pass

    def stop_server(self) -> None:
        """No-op for StatsD (client-side push, no server needed)."""
        pass
