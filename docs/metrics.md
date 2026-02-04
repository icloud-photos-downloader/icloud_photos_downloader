# Metrics

```{versionadded} 1.33.0
```

`icloudpd` supports exporting metrics for monitoring and observability. Two backends are supported: **Prometheus** and **StatsD**.

## Configuration

Enable metrics using the [`--metrics-backend`](metrics-backend-parameter) parameter:

```bash
# Prometheus only
icloudpd --username user@example.com --directory /photos --metrics-backend prometheus

# StatsD only
icloudpd --username user@example.com --directory /photos --metrics-backend statsd

# Both backends simultaneously
icloudpd --username user@example.com --directory /photos --metrics-backend both
```

## Prometheus

When using the `prometheus` backend, an HTTP server is started that exposes metrics at the `/metrics` endpoint in Prometheus exposition format.

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| [`--prometheus-host`](prometheus-host-parameter) | `0.0.0.0` | Host to bind the HTTP server |
| [`--prometheus-port`](prometheus-port-parameter) | `9090` | Port for the HTTP server |

### Example Scrape Configuration

Add the following to your Prometheus `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'icloudpd'
    static_configs:
      - targets: ['localhost:9090']
```

For Docker deployments:

```yaml
scrape_configs:
  - job_name: 'icloudpd'
    static_configs:
      - targets: ['icloudpd:9090']
```

### Docker Usage

When running icloudpd in Docker with Prometheus metrics, expose port 9090:

```bash
docker run -p 9090:9090 \
    -v /path/to/photos:/data \
    -v /path/to/cookies:/cookies \
    icloudpd/icloudpd icloudpd \
    --username user@example.com \
    --directory /data \
    --cookie-directory /cookies \
    --metrics-backend prometheus \
    --prometheus-host 0.0.0.0
```

## StatsD

When using the `statsd` backend, metrics are pushed via UDP to a StatsD server. This is useful for integration with Graphite, Datadog, or other StatsD-compatible systems.

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| [`--statsd-host`](statsd-host-parameter) | `localhost` | StatsD server host |
| [`--statsd-port`](statsd-port-parameter) | `8125` | StatsD server port |
| [`--statsd-prefix`](statsd-prefix-parameter) | `icloudpd` | Prefix for all metric names |

### Example

```bash
icloudpd --username user@example.com --directory /photos \
    --metrics-backend statsd \
    --statsd-host statsd.example.com \
    --statsd-port 8125 \
    --statsd-prefix myapp.icloudpd
```

## Available Metrics

### Counters

| Metric | Labels | Description |
|--------|--------|-------------|
| `downloads_total` | `status`, `size` | Total number of download attempts. Status is `success` or `failure`. Size indicates the asset size variant. |
| `download_bytes_total` | `size` | Total bytes downloaded successfully |
| `download_retries_total` | `reason` | Number of download retries. Reason: `session`, `throttle`, or `io` |
| `photos_processed_total` | `action` | Photos processed. Action: `downloaded`, `skipped`, or `deleted` |
| `videos_processed_total` | `action` | Videos processed. Action: `downloaded`, `skipped`, or `deleted` |
| `sync_runs_total` | `status` | Sync run completions. Status: `success`, `failure`, or `cancelled` |
| `api_requests_total` | `method`, `status_code` | Total API requests to iCloud |
| `api_errors_total` | `error_type` | API errors by type |
| `auth_attempts_total` | `result`, `method` | Authentication attempts. Result: `started`, `success`, `failure`. Method: `password`, `2fa`, `2sa`, `2fa_web` |
| `auth_mfa_requests_total` | `type` | MFA code requests. Type: `2fa` or `2sa` |

### Gauges

| Metric | Labels | Description |
|--------|--------|-------------|
| `up` | - | Set to 1 when icloudpd is running |
| `current_progress` | - | Current sync progress percentage (0-100) |

### Histograms

| Metric | Labels | Description |
|--------|--------|-------------|
| `download_duration_seconds` | `size` | Time taken to download individual files |
| `sync_duration_seconds` | - | Total duration of each sync run |
| `api_request_duration_seconds` | `method` | Duration of individual API requests |

## Multi-Instance Setup

When running multiple `icloudpd` instances (e.g., for different iCloud accounts), use the [`--metrics-instance`](metrics-instance-parameter) parameter to distinguish them:

```bash
# Instance for user1
icloudpd --username user1@example.com --directory /photos/user1 \
    --metrics-backend prometheus --prometheus-port 9091 \
    --metrics-instance user1

# Instance for user2
icloudpd --username user2@example.com --directory /photos/user2 \
    --metrics-backend prometheus --prometheus-port 9092 \
    --metrics-instance user2
```

The instance label is added to all metrics, allowing you to filter and aggregate by instance in your monitoring system.

## Example Queries

### Prometheus/PromQL

Download success rate:
```promql
sum(rate(downloads_total{status="success"}[5m])) / sum(rate(downloads_total[5m]))
```

Photos downloaded per hour:
```promql
sum(increase(photos_processed_total{action="downloaded"}[1h]))
```

Videos downloaded per hour:
```promql
sum(increase(videos_processed_total{action="downloaded"}[1h]))
```

Total assets (photos + videos) downloaded per hour:
```promql
sum(increase(photos_processed_total{action="downloaded"}[1h])) + sum(increase(videos_processed_total{action="downloaded"}[1h]))
```

Average download duration:
```promql
rate(download_duration_seconds_sum[5m]) / rate(download_duration_seconds_count[5m])
```

API error rate by type:
```promql
sum by (error_type) (rate(api_errors_total[5m]))
```

Sync success rate:
```promql
sum(rate(sync_runs_total{status="success"}[24h])) / sum(rate(sync_runs_total[24h]))
```

### Grafana Dashboard

An example Grafana dashboard is available at [`examples/grafana-dashboard.json`](https://github.com/icloud-photos-downloader/icloud_photos_downloader/blob/master/examples/grafana-dashboard.json). Import it into Grafana to get started quickly.

The dashboard includes:
- Status overview (up/down, sync runs, avg duration)
- Photos and videos processed (total and rate)
- Sync activity charts
- API requests and auth attempts

### Grafana Dashboard Tips

- Use `up` metric for availability alerting
- Track `current_progress` for real-time sync status
- Alert on `api_errors_total` increases for early warning of issues
- Use `sync_duration_seconds` histograms to track performance trends
