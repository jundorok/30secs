# 30secs

`30secs` is an ultra-lightweight system monitoring tool that **takes system snapshots every 30 seconds (default)**, or returns snapshots on-demand via **CLI**.

## Features

- **Real-time monitoring**: CPU, memory, disk, network, and process metrics
- **Multiple output formats**: JSON, human-readable table, Prometheus metrics
- **Alert system**: Configurable threshold-based alerts
- **Graceful shutdown**: Handles SIGINT/SIGTERM signals
- **Production-ready**: Structured logging, error handling, modular architecture

> ⚠️ Python module names cannot start with a number, so while the project is named `30secs`, the import package is `thirtysecs`.

---

## Installation

### Install uv (official docs)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install/sync dependencies

```bash
uv sync
```

---

## Usage

### Single snapshot (JSON output)

```bash
uv run 30secs snapshot
```

### Human-readable table output

```bash
uv run 30secs snapshot --format table
```

### Prometheus metrics format

```bash
uv run 30secs snapshot --format prometheus
```

### Continuous monitoring (every 30 seconds)

```bash
uv run 30secs watch
```

### Custom interval (every 10 seconds)

```bash
uv run 30secs watch --interval 10
```

### Watch with table format (auto-refresh)

```bash
uv run 30secs watch --format table --interval 5
```

### Quick snapshot (without processes - faster)

```bash
uv run 30secs quick
```

### Enable alerts

```bash
uv run 30secs watch --alerts
```

### Save output to file

```bash
uv run 30secs watch --output metrics.jsonl
```

### Limit number of snapshots

```bash
uv run 30secs watch --count 10 --interval 5
```

### Exclude specific metrics

```bash
uv run 30secs snapshot --no-processes --no-network
```

---

## Output Formats

### JSON (default)

Complete system metrics in JSON format, suitable for log aggregation and processing.

### Table

Human-readable format with emojis and organized sections:
- System info (hostname, OS, uptime)
- CPU (usage, cores, load average)
- Memory (used/total, available, swap)
- Disk (partitions, usage)
- Network (sent/received, connections)
- Processes (top by CPU/memory)

### Prometheus

Metrics in Prometheus exposition format, ready for scraping.

---

## Alerts

Built-in alert thresholds:
- **CPU**: > 90%
- **Memory**: > 90%, > 95% (critical)
- **Swap**: > 80%

When alerts are enabled (`--alerts`), the tool will:
- Log warnings when thresholds are exceeded
- Exit with code 1 if any alert is triggered (for `snapshot` command)

---

## Development

### Run tests

```bash
uv run pytest
```

### Linting & Formatting

```bash
uv run ruff check .
uv run ruff format .
```

### Type checking

```bash
uv run mypy src
```

---

## Project Structure

```
src/thirtysecs/
├── __init__.py          # Package init
├── __main__.py          # Entry point
├── cli.py               # CLI interface
├── config.py            # Configuration
├── core.py              # Core snapshot logic
├── alerts.py            # Alert system
├── errors.py            # Error definitions
├── logging.py           # Structured logging
├── collectors/          # Metric collectors
│   ├── base.py          # Base collector interface
│   ├── cpu.py           # CPU metrics
│   ├── memory.py        # Memory metrics
│   ├── disk.py          # Disk metrics
│   ├── network.py       # Network metrics
│   ├── process.py       # Process metrics
│   └── system.py        # System info
└── formatters/          # Output formatters
    ├── base.py          # Base formatter interface
    ├── json_fmt.py      # JSON output
    ├── table.py         # Table output
    └── prometheus.py    # Prometheus metrics
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_NAME` | `30secs` | Service name for health checks |
| `DEFAULT_INTERVAL_SECONDS` | `30` | Default watch interval |
| `INCLUDE_HOSTNAME` | `1` | Include hostname in output |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ALERT_CPU_THRESHOLD` | `90.0` | CPU usage alert threshold (%) |
| `ALERT_MEMORY_THRESHOLD` | `90.0` | Memory usage alert threshold (%) |
| `ALERT_MEMORY_CRITICAL_THRESHOLD` | `95.0` | Critical memory alert threshold (%) |
| `ALERT_SWAP_THRESHOLD` | `80.0` | Swap usage alert threshold (%) |
| `MEMORY_LEAK_WINDOW_SIZE` | `10` | Number of samples for leak detection |
| `MEMORY_LEAK_GROWTH_THRESHOLD` | `5.0` | Memory growth % to trigger leak alert |

---

## Memory Leak Detection

30secs includes automatic memory leak detection when using `--alerts`:

```bash
# Monitor with leak detection (default: 10 samples, 5% growth threshold)
30secs watch -f table --alerts -i 10

# Custom thresholds via environment variables
MEMORY_LEAK_WINDOW_SIZE=20 MEMORY_LEAK_GROWTH_THRESHOLD=3.0 30secs watch --alerts -i 5
```

The detector tracks memory usage over a sliding window and alerts when:
- Memory growth exceeds the threshold (default: 5%)
- At least 60% of samples show an increasing trend

---

## uv Cheat Sheet

| Command | Description |
|---------|-------------|
| `uv add <pkg>` | Add a dependency |
| `uv add --group dev <pkg>` | Add a dev dependency |
| `uv lock` | Lock dependencies |
| `uv sync` | Sync dependencies |
| `uv run --frozen ...` | Run with locked dependencies |

---

## License

MIT
