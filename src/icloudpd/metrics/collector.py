"""Metrics collector interface and NoOp implementation"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Dict, Generator


class MetricsCollector(ABC):
    """Abstract base class for metrics collection.

    Provides a unified interface for different metrics backends (Prometheus, StatsD, etc.).
    Uses the strategy pattern to allow swapping implementations without changing calling code.
    """

    _instance: str | None = None

    def _merge_labels(self, labels: Dict[str, str] | None) -> Dict[str, str]:
        """Merge instance label with provided labels.

        Args:
            labels: Optional labels from the caller

        Returns:
            Labels with instance added (empty string if not configured)
        """
        merged = {"instance": self._instance or ""}
        if labels:
            merged.update(labels)
        return merged

    @abstractmethod
    def inc(self, name: str, value: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        """Increment a counter metric.

        Args:
            name: The metric name (e.g., 'downloads_total')
            value: Amount to increment by (default: 1.0)
            labels: Optional labels/tags for the metric
        """
        pass

    @abstractmethod
    def set(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Set a gauge metric to a specific value.

        Args:
            name: The metric name (e.g., 'current_progress')
            value: The value to set
            labels: Optional labels/tags for the metric
        """
        pass

    @abstractmethod
    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Record an observation for a histogram/summary metric.

        Args:
            name: The metric name (e.g., 'download_duration_seconds')
            value: The observed value
            labels: Optional labels/tags for the metric
        """
        pass

    @contextmanager
    def time(self, name: str, labels: Dict[str, str] | None = None) -> Generator[None, None, None]:
        """Context manager for timing operations.

        Args:
            name: The metric name for the duration histogram
            labels: Optional labels/tags for the metric

        Example:
            with metrics.time('download_duration_seconds', {'size': 'original'}):
                download_file()
        """
        import time

        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.observe(name, duration, labels)

    @abstractmethod
    def start_server(self) -> None:
        """Start the metrics server (if applicable for the backend)."""
        pass

    @abstractmethod
    def stop_server(self) -> None:
        """Stop the metrics server (if applicable for the backend)."""
        pass


class NoOpCollector(MetricsCollector):
    """No-operation metrics collector.

    Used when metrics are disabled. All methods are no-ops with minimal overhead.
    This is the default collector when --metrics-backend is 'none'.
    """

    def inc(self, name: str, value: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        """No-op increment."""
        pass

    def set(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """No-op set."""
        pass

    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """No-op observe."""
        pass

    @contextmanager
    def time(self, name: str, labels: Dict[str, str] | None = None) -> Generator[None, None, None]:
        """No-op timer - yields without measuring."""
        yield

    def start_server(self) -> None:
        """No-op start server."""
        pass

    def stop_server(self) -> None:
        """No-op stop server."""
        pass


class CompositeCollector(MetricsCollector):
    """Composite collector that delegates to multiple backends.

    Used when --metrics-backend is 'both' to send metrics to both
    Prometheus and StatsD simultaneously.
    """

    def __init__(self, collectors: list[MetricsCollector]) -> None:
        self._collectors = collectors

    def inc(self, name: str, value: float = 1.0, labels: Dict[str, str] | None = None) -> None:
        """Increment on all collectors."""
        for collector in self._collectors:
            collector.inc(name, value, labels)

    def set(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Set on all collectors."""
        for collector in self._collectors:
            collector.set(name, value, labels)

    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        """Observe on all collectors."""
        for collector in self._collectors:
            collector.observe(name, value, labels)

    def start_server(self) -> None:
        """Start server on all collectors."""
        for collector in self._collectors:
            collector.start_server()

    def stop_server(self) -> None:
        """Stop server on all collectors."""
        for collector in self._collectors:
            collector.stop_server()
