import logging
from threading import Thread
from typing import Any, Dict

from icloudpd.metrics.collector import MetricsCollector

LOGGER = logging.getLogger(__name__)

# Global storage for Prometheus metrics to avoid duplicate registration
_PROMETHEUS_METRICS: Dict[str, Any] = {}


class PrometheusCollector(MetricsCollector):
    """Prometheus metrics collector with HTTP server.

    Exposes metrics on a dedicated HTTP endpoint for Prometheus scraping.
    Uses prometheus_client library for metric types and HTTP server.
    """

    def __init__(
        self, host: str = "0.0.0.0", port: int = 9090, instance: str | None = None
    ) -> None:
        """Initialize Prometheus collector.

        Args:
            host: Host to bind the HTTP server (default: 0.0.0.0)
            port: Port for the HTTP server (default: 9090)
            instance: Optional instance label to add to all metrics
        """
        self._host = host
        self._port = port
        self._instance = instance
        self._server: Thread | None = None
        self._server_started = False

        global _PROMETHEUS_METRICS

        # Import prometheus_client here to make it an optional dependency
        try:
            from prometheus_client import REGISTRY, Counter, Gauge, Histogram

            self._prometheus_available = True
        except ImportError:
            LOGGER.warning(
                "prometheus_client not installed. Prometheus metrics will be disabled. "
                "Install with: pip install prometheus_client"
            )
            self._prometheus_available = False
            return

        # Use global metrics dictionary to ensure metrics are only registered once
        # This handles both tests (multiple instances) and application restarts
        if not _PROMETHEUS_METRICS:
            # First time initialization - create all metrics
            _PROMETHEUS_METRICS["downloads_total"] = Counter(
                "icloudpd_downloads_total",
                "Total number of download operations",
                ["instance", "status", "size"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["download_bytes_total"] = Counter(
                "icloudpd_download_bytes_total",
                "Total bytes downloaded",
                ["instance", "size"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["download_duration_seconds"] = Histogram(
                "icloudpd_download_duration_seconds",
                "Time spent downloading files",
                ["instance", "size"],
                buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["download_retries_total"] = Counter(
                "icloudpd_download_retries_total",
                "Total number of download retries",
                ["instance", "reason"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["api_requests_total"] = Counter(
                "icloudpd_api_requests_total",
                "Total number of API requests",
                ["instance", "method", "status_code"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["api_request_duration_seconds"] = Histogram(
                "icloudpd_api_request_duration_seconds",
                "Time spent on API requests",
                ["instance", "method"],
                buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["api_errors_total"] = Counter(
                "icloudpd_api_errors_total",
                "Total number of API errors",
                ["instance", "error_type"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["auth_attempts_total"] = Counter(
                "icloudpd_auth_attempts_total",
                "Total number of authentication attempts",
                ["instance", "result", "method"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["auth_mfa_requests_total"] = Counter(
                "icloudpd_auth_mfa_requests_total",
                "Total number of MFA requests",
                ["instance", "type"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["photos_processed_total"] = Counter(
                "icloudpd_photos_processed_total",
                "Total number of photos processed",
                ["instance", "action"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["videos_processed_total"] = Counter(
                "icloudpd_videos_processed_total",
                "Total number of videos processed",
                ["instance", "action"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["sync_runs_total"] = Counter(
                "icloudpd_sync_runs_total",
                "Total number of sync runs",
                ["instance", "status"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["sync_duration_seconds"] = Histogram(
                "icloudpd_sync_duration_seconds",
                "Time spent on sync operations",
                ["instance"],
                buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0, float("inf")),
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["current_progress"] = Gauge(
                "icloudpd_current_progress",
                "Current progress percentage",
                ["instance"],
                registry=REGISTRY,
            )
            _PROMETHEUS_METRICS["up"] = Gauge(
                "icloudpd_up",
                "Whether icloudpd is running",
                ["instance"],
                registry=REGISTRY,
            )

        # Reference the global metrics
        self._downloads_total = _PROMETHEUS_METRICS["downloads_total"]
        self._download_bytes_total = _PROMETHEUS_METRICS["download_bytes_total"]
        self._download_duration_seconds = _PROMETHEUS_METRICS["download_duration_seconds"]
        self._download_retries_total = _PROMETHEUS_METRICS["download_retries_total"]
        self._api_requests_total = _PROMETHEUS_METRICS["api_requests_total"]
        self._api_request_duration_seconds = _PROMETHEUS_METRICS["api_request_duration_seconds"]
        self._api_errors_total = _PROMETHEUS_METRICS["api_errors_total"]
        self._auth_attempts_total = _PROMETHEUS_METRICS["auth_attempts_total"]
        self._auth_mfa_requests_total = _PROMETHEUS_METRICS["auth_mfa_requests_total"]
        self._photos_processed_total = _PROMETHEUS_METRICS["photos_processed_total"]
        self._videos_processed_total = _PROMETHEUS_METRICS["videos_processed_total"]
        self._sync_runs_total = _PROMETHEUS_METRICS["sync_runs_total"]
        self._sync_duration_seconds = _PROMETHEUS_METRICS["sync_duration_seconds"]
        self._current_progress = _PROMETHEUS_METRICS["current_progress"]
        self._up = _PROMETHEUS_METRICS["up"]

        # Map metric names to their prometheus objects and types
        self._counters: Dict[str, Counter] = {
            "downloads_total": self._downloads_total,
            "download_bytes_total": self._download_bytes_total,
            "download_retries_total": self._download_retries_total,
            "api_requests_total": self._api_requests_total,
            "api_errors_total": self._api_errors_total,
            "auth_attempts_total": self._auth_attempts_total,
            "auth_mfa_requests_total": self._auth_mfa_requests_total,
            "photos_processed_total": self._photos_processed_total,
            "videos_processed_total": self._videos_processed_total,
            "sync_runs_total": self._sync_runs_total,
        }
        self._histograms: Dict[str, Histogram] = {
            "download_duration_seconds": self._download_duration_seconds,
            "api_request_duration_seconds": self._api_request_duration_seconds,
            "sync_duration_seconds": self._sync_duration_seconds,
        }
        self._gauges: Dict[str, Gauge] = {
            "current_progress": self._current_progress,
            "up": self._up,
        }

    def inc(self, name: str, value: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        if not self._prometheus_available:
            return

        merged = self._merge_labels(labels)
        if name in self._counters:
            counter = self._counters[name]
            counter.labels(**merged).inc(value)
        else:
            LOGGER.debug(f"Unknown counter metric: {name}")

    def set(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        if not self._prometheus_available:
            return

        merged = self._merge_labels(labels)
        if name in self._gauges:
            gauge = self._gauges[name]
            gauge.labels(**merged).set(value)
        else:
            LOGGER.debug(f"Unknown gauge metric: {name}")

    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Record an observation for a histogram."""
        if not self._prometheus_available:
            return

        merged = self._merge_labels(labels)
        if name in self._histograms:
            histogram = self._histograms[name]
            histogram.labels(**merged).observe(value)
        else:
            LOGGER.debug(f"Unknown histogram metric: {name}")

    def start_server(self) -> None:
        """Start the Prometheus HTTP server in a daemon thread."""
        if not self._prometheus_available:
            return

        if self._server_started:
            return

        from prometheus_client import start_http_server

        try:
            start_http_server(self._port, addr=self._host)
            self._server_started = True
            LOGGER.info(f"Prometheus metrics server started on {self._host}:{self._port}")
        except OSError as e:
            LOGGER.error(f"Failed to start Prometheus server on {self._host}:{self._port}: {e}")

    def stop_server(self) -> None:
        """Stop the Prometheus HTTP server.

        Note: prometheus_client's start_http_server doesn't provide a clean way to stop.
        The server runs in a daemon thread, so it will stop when the main process exits.
        """
        self._server_started = False
