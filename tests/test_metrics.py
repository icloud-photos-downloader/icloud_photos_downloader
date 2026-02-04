"""Tests for the metrics module"""

import time
from unittest.mock import MagicMock, patch

from icloudpd.config import MetricsBackend, MetricsConfig
from icloudpd.metrics import (
    CompositeCollector,
    MetricsCollector,
    NoOpCollector,
    create_metrics_collector,
)
from icloudpd.metrics.prometheus_collector import PrometheusCollector
from icloudpd.metrics.statsd_collector import StatsDCollector


class TestNoOpCollector:
    """Tests for the NoOpCollector"""

    def test_inc_does_nothing(self):
        """Test that inc method is a no-op"""
        collector = NoOpCollector()
        # Should not raise any exceptions
        collector.inc("test_counter")
        collector.inc("test_counter", value=5.0)
        collector.inc("test_counter", labels={"label1": "value1"})
        collector.inc("test_counter", value=10.0, labels={"label1": "value1"})

    def test_set_does_nothing(self):
        """Test that set method is a no-op"""
        collector = NoOpCollector()
        # Should not raise any exceptions
        collector.set("test_gauge", 42.0)
        collector.set("test_gauge", 100.0, labels={"label1": "value1"})

    def test_observe_does_nothing(self):
        """Test that observe method is a no-op"""
        collector = NoOpCollector()
        # Should not raise any exceptions
        collector.observe("test_histogram", 1.5)
        collector.observe("test_histogram", 2.5, labels={"label1": "value1"})

    def test_time_context_manager_yields_immediately(self):
        """Test that time context manager yields without measuring"""
        collector = NoOpCollector()
        start = time.perf_counter()
        with collector.time("test_duration"):
            pass
        elapsed = time.perf_counter() - start
        # Should complete almost instantly (no actual timing)
        assert elapsed < 0.01

    def test_start_stop_server_does_nothing(self):
        """Test that server methods are no-ops"""
        collector = NoOpCollector()
        # Should not raise any exceptions
        collector.start_server()
        collector.stop_server()


class TestCompositeCollector:
    """Tests for the CompositeCollector"""

    def test_inc_delegates_to_all_collectors(self):
        """Test that inc is called on all collectors"""
        collector1 = MagicMock(spec=MetricsCollector)
        collector2 = MagicMock(spec=MetricsCollector)
        composite = CompositeCollector([collector1, collector2])

        composite.inc("test_counter", value=5.0, labels={"key": "value"})

        collector1.inc.assert_called_once_with("test_counter", 5.0, {"key": "value"})
        collector2.inc.assert_called_once_with("test_counter", 5.0, {"key": "value"})

    def test_set_delegates_to_all_collectors(self):
        """Test that set is called on all collectors"""
        collector1 = MagicMock(spec=MetricsCollector)
        collector2 = MagicMock(spec=MetricsCollector)
        composite = CompositeCollector([collector1, collector2])

        composite.set("test_gauge", 42.0, labels={"key": "value"})

        collector1.set.assert_called_once_with("test_gauge", 42.0, {"key": "value"})
        collector2.set.assert_called_once_with("test_gauge", 42.0, {"key": "value"})

    def test_observe_delegates_to_all_collectors(self):
        """Test that observe is called on all collectors"""
        collector1 = MagicMock(spec=MetricsCollector)
        collector2 = MagicMock(spec=MetricsCollector)
        composite = CompositeCollector([collector1, collector2])

        composite.observe("test_histogram", 1.5, labels={"key": "value"})

        collector1.observe.assert_called_once_with("test_histogram", 1.5, {"key": "value"})
        collector2.observe.assert_called_once_with("test_histogram", 1.5, {"key": "value"})

    def test_start_server_delegates_to_all_collectors(self):
        """Test that start_server is called on all collectors"""
        collector1 = MagicMock(spec=MetricsCollector)
        collector2 = MagicMock(spec=MetricsCollector)
        composite = CompositeCollector([collector1, collector2])

        composite.start_server()

        collector1.start_server.assert_called_once()
        collector2.start_server.assert_called_once()

    def test_stop_server_delegates_to_all_collectors(self):
        """Test that stop_server is called on all collectors"""
        collector1 = MagicMock(spec=MetricsCollector)
        collector2 = MagicMock(spec=MetricsCollector)
        composite = CompositeCollector([collector1, collector2])

        composite.stop_server()

        collector1.stop_server.assert_called_once()
        collector2.stop_server.assert_called_once()


class TestPrometheusCollector:
    """Tests for the PrometheusCollector"""

    def test_inc_counter(self):
        """Test incrementing a counter"""
        collector = PrometheusCollector(host="127.0.0.1", port=19090)
        # Should not raise
        collector.inc("downloads_total", labels={"status": "success", "size": "original"})
        collector.inc("downloads_total", value=5.0, labels={"status": "failure", "size": "medium"})

    def test_set_gauge(self):
        """Test setting a gauge"""
        collector = PrometheusCollector(host="127.0.0.1", port=18101)
        # Should not raise
        collector.set("current_progress", 50.0)
        collector.set("up", 1.0)

    def test_observe_histogram(self):
        """Test observing a histogram"""
        collector = PrometheusCollector(host="127.0.0.1", port=18102)
        # Should not raise
        collector.observe("download_duration_seconds", 1.5, labels={"size": "original"})
        collector.observe("api_request_duration_seconds", 0.5, labels={"method": "GET"})

    def test_unknown_metric_logs_debug(self):
        """Test that unknown metrics log debug message"""
        collector = PrometheusCollector(host="127.0.0.1", port=18103)
        # Should not raise, just log debug
        collector.inc("unknown_counter")
        collector.set("unknown_gauge", 1.0)
        collector.observe("unknown_histogram", 1.0)


class TestStatsDCollector:
    """Tests for the StatsDCollector"""

    def test_build_metric_name_without_labels(self):
        """Test metric name building without labels"""
        collector = StatsDCollector(host="127.0.0.1", port=18125, prefix="test")
        name = collector._build_metric_name("downloads_total", None)
        assert name == "downloads_total"

    def test_build_metric_name_with_labels(self):
        """Test metric name building with labels"""
        collector = StatsDCollector(host="127.0.0.1", port=18126, prefix="test")
        name = collector._build_metric_name(
            "downloads_total", {"status": "success", "size": "original"}
        )
        # Labels should be sorted alphabetically
        assert name == "downloads_total.size_original.status_success"

    def test_inc_sends_to_client(self):
        """Test that inc calls the statsd client"""
        collector = StatsDCollector(host="127.0.0.1", port=18127, prefix="test")
        if collector._client:
            with patch.object(collector._client, "incr") as mock_incr:
                collector.inc("downloads_total", value=5.0, labels={"status": "success"})
                mock_incr.assert_called_once_with("downloads_total.status_success", 5)

    def test_set_sends_to_client(self):
        """Test that set calls the statsd client"""
        collector = StatsDCollector(host="127.0.0.1", port=18128, prefix="test")
        if collector._client:
            with patch.object(collector._client, "gauge") as mock_gauge:
                collector.set("current_progress", 75.0)
                mock_gauge.assert_called_once_with("current_progress", 75.0)

    def test_observe_sends_to_client(self):
        """Test that observe calls the statsd client timing in milliseconds"""
        collector = StatsDCollector(host="127.0.0.1", port=18129, prefix="test")
        if collector._client:
            with patch.object(collector._client, "timing") as mock_timing:
                collector.observe("download_duration_seconds", 1.5)
                # Value should be converted to milliseconds
                mock_timing.assert_called_once_with("download_duration_seconds", 1500.0)

    def test_instance_label_merged_into_metrics(self):
        """Test that instance label is merged into metric names"""
        collector = StatsDCollector(host="127.0.0.1", port=18130, prefix="test", instance="user1")
        if collector._client:
            with patch.object(collector._client, "incr") as mock_incr:
                collector.inc("downloads_total", value=1.0, labels={"status": "success"})
                # instance should be merged with other labels
                mock_incr.assert_called_once_with(
                    "downloads_total.instance_user1.status_success", 1
                )

    def test_instance_label_only_when_no_other_labels(self):
        """Test that instance label is added when no other labels provided"""
        collector = StatsDCollector(host="127.0.0.1", port=18131, prefix="test", instance="user2")
        if collector._client:
            with patch.object(collector._client, "gauge") as mock_gauge:
                collector.set("up", 1.0)
                mock_gauge.assert_called_once_with("up.instance_user2", 1.0)


class TestCreateMetricsCollector:
    """Tests for the create_metrics_collector factory function"""

    def test_none_backend_returns_noop(self):
        """Test that 'none' backend returns NoOpCollector"""
        collector = create_metrics_collector(backend="none")
        assert isinstance(collector, NoOpCollector)

    def test_prometheus_backend_returns_prometheus(self):
        """Test that 'prometheus' backend returns PrometheusCollector"""
        collector = create_metrics_collector(
            backend="prometheus",
            prometheus_host="127.0.0.1",
            prometheus_port=18200,
        )
        assert isinstance(collector, PrometheusCollector)

    def test_statsd_backend_returns_statsd(self):
        """Test that 'statsd' backend returns StatsDCollector"""
        collector = create_metrics_collector(
            backend="statsd",
            statsd_host="127.0.0.1",
            statsd_port=18201,
            statsd_prefix="test",
        )
        assert isinstance(collector, StatsDCollector)

    def test_both_backend_returns_composite(self):
        """Test that 'both' backend returns CompositeCollector"""
        collector = create_metrics_collector(
            backend="both",
            prometheus_host="127.0.0.1",
            prometheus_port=18202,
            statsd_host="127.0.0.1",
            statsd_port=18203,
            statsd_prefix="test",
        )
        assert isinstance(collector, CompositeCollector)

    def test_unknown_backend_returns_noop(self):
        """Test that unknown backend returns NoOpCollector"""
        collector = create_metrics_collector(backend="unknown")
        assert isinstance(collector, NoOpCollector)

    def test_instance_passed_to_collectors(self):
        """Test that instance is passed to collectors"""
        collector = create_metrics_collector(
            backend="statsd",
            statsd_host="127.0.0.1",
            statsd_port=18204,
            statsd_prefix="test",
            instance="user1",
        )
        assert isinstance(collector, StatsDCollector)
        assert collector._instance == "user1"


class TestMetricsCollectorTimeContextManager:
    """Tests for the time context manager on MetricsCollector"""

    def test_time_measures_duration(self):
        """Test that time context manager measures and observes duration"""
        # For this test, we'll use a concrete collector and verify observe is called

        class TestCollector(MetricsCollector):
            def __init__(self):
                self.observed_values = []

            def inc(self, name, value=1.0, labels=None):
                pass

            def set(self, name, value, labels=None):
                pass

            def observe(self, name, value, labels=None):
                self.observed_values.append((name, value, labels))

            def start_server(self):
                pass

            def stop_server(self):
                pass

        collector = TestCollector()
        with collector.time("test_duration", {"label": "value"}):
            time.sleep(0.01)  # Sleep for 10ms

        assert len(collector.observed_values) == 1
        name, value, labels = collector.observed_values[0]
        assert name == "test_duration"
        assert value >= 0.01  # At least 10ms
        assert value < 0.5  # But less than 500ms (reasonable upper bound)
        assert labels == {"label": "value"}


class TestMetricsConfig:
    """Tests for MetricsConfig dataclass"""

    def test_metrics_config_creation(self):
        """Test creating a MetricsConfig"""
        config = MetricsConfig(
            backend=MetricsBackend.PROMETHEUS,
            prometheus_host="0.0.0.0",
            prometheus_port=9090,
            statsd_host="localhost",
            statsd_port=8125,
            statsd_prefix="icloudpd",
            instance="user1",
        )
        assert config.backend == MetricsBackend.PROMETHEUS
        assert config.prometheus_host == "0.0.0.0"
        assert config.prometheus_port == 9090
        assert config.statsd_host == "localhost"
        assert config.statsd_port == 8125
        assert config.statsd_prefix == "icloudpd"
        assert config.instance == "user1"

    def test_metrics_config_with_no_instance(self):
        """Test creating a MetricsConfig without instance"""
        config = MetricsConfig(
            backend=MetricsBackend.NONE,
            prometheus_host="0.0.0.0",
            prometheus_port=9090,
            statsd_host="localhost",
            statsd_port=8125,
            statsd_prefix="icloudpd",
            instance=None,
        )
        assert config.instance is None

    def test_metrics_backend_enum_values(self):
        """Test MetricsBackend enum values"""
        assert MetricsBackend.NONE.value == "none"
        assert MetricsBackend.PROMETHEUS.value == "prometheus"
        assert MetricsBackend.STATSD.value == "statsd"
        assert MetricsBackend.BOTH.value == "both"
