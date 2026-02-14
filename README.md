# 30secs

`30secs` is an ultra-lightweight system monitoring tool that **takes system snapshots every 30 seconds (default)**, or returns snapshots on-demand via **CLI**.

- Package manager: **uv**
- Runtime dependency: `psutil`
- Features:
  - CLI: `30secs snapshot`, `30secs watch`
  - Monitor CPU, memory, disk, and network status of all nodes

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

### Single snapshot (shows all node status)

```bash
uv run 30secs snapshot
```

### Continuous monitoring every 30 seconds (default)

```bash
uv run 30secs watch
```

### Custom interval (e.g., every 10 seconds)

```bash
uv run 30secs watch --interval 10
```

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
