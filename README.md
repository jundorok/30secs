# 30secs

`30secs` is an ultra-lightweight system monitoring tool that **takes system snapshots every 30 seconds (default)**, or returns snapshots on-demand via **CLI**.

## Features

- **Real-time monitoring**: CPU, memory, disk, network, and process metrics
- **Memory leak analysis**: Per-process leak scoring with linear regression, R² confidence, and resource correlation (threads, FDs, connections)
- **OOM killer detection**: Parse kernel OOM kill events from dmesg/journal with process and cgroup details
- **Container-aware**: cgroup v1/v2 memory limits, usage, and pressure (PSI) for Kubernetes environments
- **Deep Python analysis**: tracemalloc-based line-level and type-level memory growth detection
- **Kernel memory details**: Buffers, Cached, Slab, PageTables, HugePages from /proc/meminfo
- **Process deep-dive**: smaps_rollup mapping breakdown, page fault counters, USS/PSS metrics
- **Multiple output formats**: JSON, human-readable table, Prometheus metrics
- **Alert system**: Configurable threshold-based alerts with leak detection cooldown
- **Graceful shutdown**: Handles SIGINT/SIGTERM signals
- **Production-ready**: Structured logging, error handling, modular architecture

> ⚠️ Python module names cannot start with a number, so while the project is named `30secs`, the import package is `thirtysecs`.

---

## Installation

### Binary (No Python Required) - Recommended for K8s Nodes

Download the pre-built binary for your platform:

```bash
# Linux AMD64 (most K8s nodes)
curl -L https://github.com/<your-repo>/30secs/releases/latest/download/30secs-linux-amd64 -o 30secs

# Linux ARM64 (Graviton, etc.)
curl -L https://github.com/<your-repo>/30secs/releases/latest/download/30secs-linux-arm64 -o 30secs

# Make executable and run
chmod +x 30secs
./30secs watch -f table --alerts
```

#### One-liner for K8s Node Debugging

```bash
curl -sL https://github.com/<your-repo>/30secs/releases/latest/download/30secs-linux-amd64 -o /tmp/30secs \
  && chmod +x /tmp/30secs \
  && /tmp/30secs watch -f table --alerts -i 10
```

### pip (PyPI) - Recommended for environments without GitHub access

```bash
# Install from PyPI (Python 3.11+ required)
pip install 30secs

# Or use pipx for isolated install
pipx install 30secs

# Or use uv
uv tool install 30secs

# Then run
30secs watch -f table --alerts -i 10
```

#### One-liner for K8s Node (pip)

```bash
pip install 30secs && 30secs watch -f table --alerts -i 10
```

### From Source (uv)

#### Install uv (official docs)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Install/sync dependencies

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

### Memory leak report for a process

```bash
# Sample a process 30 times at 2s intervals and display a leak score
uv run 30secs leak <PID> --interval 2 --count 30

# The report includes:
#   - Leak score (0-100) with confidence level
#   - RSS/USS/PSS growth and linear regression (slope, R²)
#   - Resource correlation warnings (threads, FDs, connections)
#   - smaps_rollup data and page fault counters (Linux)
```

### Memory leak report as JSON

```bash
uv run 30secs leak <PID> --format json --interval 1 --count 60
```

### Rank top leak candidates

```bash
# Find the 5 most memory-heavy processes and rank them by leak likelihood
uv run 30secs leak top --interval 1 --count 20 --limit 5
```

### Deep Python analysis with tracemalloc

```bash
# Run a script and report top growing file:line and object types
uv run 30secs leak --deep-python --script app.py --script-args "--mode stress --iterations 2000"

# Or run a module
uv run 30secs leak --deep-python --module myservice.main --script-args "--port 8080"
```

Note:
- `--deep-python` analyzes allocations after tracer start.
- It runs the target in-process (not attach-to-existing-PID mode).

### Check for OOM killer events

```bash
# Show recent OOM kills from dmesg and systemd journal
uv run 30secs oom

# Save as JSON (includes cgroup/memcg info for K8s debugging)
uv run 30secs oom -f json -o oom-events.json
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
├── cli.py               # CLI entrypoint and parser wiring
├── leak_report.py       # Leak scoring with linear regression and resource correlation
├── deep_python.py       # Deep Python tracemalloc analysis
├── oom.py               # OOM killer event detection (dmesg/journal parsing)
├── config.py            # Configuration
├── core.py              # Core snapshot logic
├── alerts.py            # Alert system with leak detection cooldown
├── errors.py            # Error definitions
├── logging.py           # Structured logging
├── commands/            # Command handlers
│   ├── leak.py          # `leak` and `leak top` handlers
│   └── oom.py           # `oom` command handler
├── collectors/          # Metric collectors
│   ├── base.py          # Base collector interface
│   ├── cpu.py           # CPU metrics
│   ├── memory.py        # Memory metrics (+ cgroup, PSI, /proc/meminfo)
│   ├── disk.py          # Disk metrics
│   ├── network.py       # Network metrics
│   ├── process.py       # Process metrics (+ smaps_rollup, page faults)
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

### Continuous monitoring (--alerts)

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
- Alerts include the linear regression slope (%/sample) for rate estimation
- A cooldown period suppresses repeat alerts to avoid alert storms

### On-demand leak analysis (leak command)

The `leak` command provides deeper per-process analysis:

```bash
# Analyze a single process (more samples = more accurate)
30secs leak <PID> -i 2 -n 30

# Rank the top 5 memory-heavy processes by leak score
30secs leak top -i 1 -n 20 -l 5
```

**How scoring works:**

| Confidence | Score | Criteria |
|------------|-------|----------|
| **High** | 85-95 | RSS growth >= 15%, trend >= 70%, high R² linear fit |
| **Medium** | 60-70 | RSS growth >= 7%, trend >= 60% |
| **Low** | 35-40 | RSS growth >= 3%, trend >= 55%, or slow-but-linear growth (R² >= 0.8) |
| **None** | 10 | No leak pattern detected |

The analysis also checks for correlated resource leaks — growing thread counts, open file descriptors, or network connections are flagged as resource warnings.

### OOM killer events (oom command)

```bash
# Check if the OOM killer has been active
30secs oom

# JSON output with cgroup details (useful for K8s pod eviction debugging)
30secs oom -f json
```

Parses kernel OOM kill events from both `dmesg` and `journalctl`, showing:
- Which processes were killed and their memory usage at kill time
- cgroup membership (identifies which Kubernetes pod/container was affected)
- The most frequently killed process name

### Container / Kubernetes memory

When running inside a container, `30secs snapshot` now automatically includes:
- **cgroup memory limits** (v1 and v2): the actual memory limit enforced by Kubernetes, not just the node's total RAM
- **cgroup usage as percent of limit**: so you can see how close you are to OOM
- **Memory pressure (PSI)**: `avg10`, `avg60`, `avg300` pressure stall metrics — if pressure is high, the system is thrashing even before the OOM killer fires
- **Kernel memory details**: Slab, PageTables, KernelStack, Buffers, Cached — helps distinguish userspace leaks from kernel memory growth

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
