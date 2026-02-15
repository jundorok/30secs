"""Memory leak sampling and report analysis utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class LeakSample:
    """Single process sample for leak analysis."""

    timestamp: str
    rss: int
    uss: int | None
    pss: int | None
    threads: int
    open_files: int
    connections: int


@dataclass
class MetricDelta:
    """Delta summary for one metric."""

    start: float
    end: float
    growth: float
    growth_percent: float | None
    increasing_ratio: float


@dataclass
class LeakAnalysis:
    """Final memory leak analysis result."""

    sample_count: int
    duration_seconds: float
    rss: MetricDelta
    uss: MetricDelta | None
    pss: MetricDelta | None
    threads: MetricDelta
    open_files: MetricDelta
    connections: MetricDelta
    confidence: str
    score: int
    diagnosis: str


def sample_from_process_detail(detail: dict[str, Any]) -> LeakSample:
    """Build a leak sample from process detail payload."""
    memory = detail.get("memory", {})
    threads = detail.get("threads", {})
    open_files = detail.get("open_files", {})
    connections = detail.get("connections", {})
    return LeakSample(
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        rss=int(memory.get("rss", 0)),
        uss=int(memory["uss"]) if memory.get("uss") is not None else None,
        pss=int(memory["pss"]) if memory.get("pss") is not None else None,
        threads=int(threads.get("count", 0)),
        open_files=int(open_files.get("count", 0)),
        connections=int(connections.get("count", 0)),
    )


def _increasing_ratio(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    increases = sum(1 for i in range(1, len(values)) if values[i] > values[i - 1])
    return increases / (len(values) - 1)


def _metric_delta(values: list[float]) -> MetricDelta:
    start = values[0]
    end = values[-1]
    growth = end - start
    growth_percent = None
    if start > 0:
        growth_percent = (growth / start) * 100.0
    return MetricDelta(
        start=start,
        end=end,
        growth=growth,
        growth_percent=growth_percent,
        increasing_ratio=_increasing_ratio(values),
    )


def _optional_metric_delta(values: list[int | None]) -> MetricDelta | None:
    filtered = [float(v) for v in values if v is not None]
    if len(filtered) < 2:
        return None
    return _metric_delta(filtered)


def _confidence_from_metrics(rss: MetricDelta, uss: MetricDelta | None) -> tuple[str, int, str]:
    rss_growth_pct = rss.growth_percent or 0.0
    rss_trend = rss.increasing_ratio
    uss_growth_pct = uss.growth_percent if uss and uss.growth_percent is not None else 0.0

    if rss_growth_pct >= 15.0 and rss_trend >= 0.7:
        if uss and uss_growth_pct >= 10.0:
            return (
                "high",
                90,
                "RSS and USS both trend upward strongly (likely real retention leak).",
            )
        return ("high", 80, "RSS grows strongly with consistent upward trend.")
    if rss_growth_pct >= 7.0 and rss_trend >= 0.6:
        if uss and uss_growth_pct >= 5.0:
            return ("medium", 70, "Moderate RSS/USS growth with upward trend.")
        return ("medium", 60, "Moderate RSS growth trend; verify with longer capture.")
    if rss_growth_pct >= 3.0 and rss_trend >= 0.55:
        return ("low", 40, "Early growth signal detected; capture longer window to confirm.")
    return ("none", 10, "No strong leak pattern in current capture window.")


def analyze_samples(samples: list[LeakSample], interval_seconds: float) -> LeakAnalysis:
    """Analyze a sequence of leak samples."""
    if not samples:
        raise ValueError("samples cannot be empty")

    rss = _metric_delta([float(s.rss) for s in samples])
    uss = _optional_metric_delta([s.uss for s in samples])
    pss = _optional_metric_delta([s.pss for s in samples])
    threads = _metric_delta([float(s.threads) for s in samples])
    open_files = _metric_delta([float(s.open_files) for s in samples])
    connections = _metric_delta([float(s.connections) for s in samples])

    confidence, score, diagnosis = _confidence_from_metrics(rss, uss)
    duration = max(0.0, (len(samples) - 1) * interval_seconds)

    return LeakAnalysis(
        sample_count=len(samples),
        duration_seconds=duration,
        rss=rss,
        uss=uss,
        pss=pss,
        threads=threads,
        open_files=open_files,
        connections=connections,
        confidence=confidence,
        score=score,
        diagnosis=diagnosis,
    )
