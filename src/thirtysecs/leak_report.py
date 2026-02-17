"""Memory leak sampling and report analysis utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
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
    slope: float = 0.0
    r_squared: float = 0.0


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
    resource_correlated: bool = False
    resource_warnings: list[str] = field(default_factory=list)


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


def _linear_regression(values: list[float]) -> tuple[float, float]:
    """Return (slope, r_squared) via ordinary least squares.

    Slope is in units-per-sample.  R-squared indicates goodness of fit
    (1.0 = perfect linear trend, 0.0 = no trend).
    """
    n = len(values)
    if n < 2:
        return 0.0, 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    ss_xy = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    ss_xx = sum((i - x_mean) ** 2 for i in range(n))
    ss_yy = sum((v - y_mean) ** 2 for v in values)
    if ss_xx == 0 or ss_yy == 0:
        return 0.0, 0.0
    slope = ss_xy / ss_xx
    r_squared = (ss_xy**2) / (ss_xx * ss_yy)
    return slope, r_squared


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
    slope, r_squared = _linear_regression(values)
    return MetricDelta(
        start=start,
        end=end,
        growth=growth,
        growth_percent=growth_percent,
        increasing_ratio=_increasing_ratio(values),
        slope=slope,
        r_squared=r_squared,
    )


def _optional_metric_delta(values: list[int | None]) -> MetricDelta | None:
    filtered = [float(v) for v in values if v is not None]
    if len(filtered) < 2:
        return None
    return _metric_delta(filtered)


def _confidence_from_metrics(
    rss: MetricDelta,
    uss: MetricDelta | None,
    sample_count: int,
) -> tuple[str, int, str]:
    rss_growth_pct = rss.growth_percent or 0.0
    rss_trend = rss.increasing_ratio
    rss_r2 = rss.r_squared
    uss_growth_pct = uss.growth_percent if uss and uss.growth_percent is not None else 0.0
    uss_r2 = uss.r_squared if uss else 0.0

    # Penalise very short capture windows — the fewer samples, the more
    # likely a growth signal is just noise.  A minimum of 5 samples is
    # needed for "medium" and 8 for "high".
    short_window = sample_count < 5
    very_short_window = sample_count < 3

    if very_short_window:
        # Two samples can never be conclusive; report only an early signal
        # even when numbers look dramatic.
        if rss_growth_pct >= 3.0 and rss_trend >= 0.5:
            return (
                "low",
                30,
                "Only 2 samples captured — early signal but insufficient data.",
            )
        return ("none", 10, "Not enough samples for meaningful analysis.")

    # ── High confidence ──────────────────────────────────────────────
    if rss_growth_pct >= 15.0 and rss_trend >= 0.7 and rss_r2 >= 0.6 and not short_window:
        if uss and uss_growth_pct >= 10.0 and uss_r2 >= 0.5:
            return (
                "high",
                95,
                "RSS and USS both trend upward strongly with high R² "
                "(likely real retention leak).",
            )
        return (
            "high",
            85,
            "RSS grows strongly with consistent upward trend "
            f"(R²={rss_r2:.2f}).",
        )
    # Legacy path: strong growth but weak linear fit (noisy signal)
    if rss_growth_pct >= 15.0 and rss_trend >= 0.7 and not short_window:
        if uss and uss_growth_pct >= 10.0:
            return (
                "high",
                80,
                "RSS and USS grow strongly (noisy trend, "
                "capture longer window).",
            )
        return ("high", 75, "RSS grows strongly with consistent upward trend.")

    # ── Medium confidence ────────────────────────────────────────────
    if rss_growth_pct >= 7.0 and rss_trend >= 0.6:
        if uss and uss_growth_pct >= 5.0:
            return ("medium", 70, "Moderate RSS/USS growth with upward trend.")
        return ("medium", 60, "Moderate RSS growth trend; verify with longer capture.")

    # ── Low confidence ───────────────────────────────────────────────
    if rss_growth_pct >= 3.0 and rss_trend >= 0.55 and rss_r2 >= 0.3:
        return ("low", 40, "Early growth signal detected; capture longer window to confirm.")

    # Linear fit may catch slow leaks that miss the threshold gates above.
    if rss.slope > 0 and rss_r2 >= 0.8 and rss_growth_pct >= 1.0:
        return (
            "low",
            35,
            f"Slow but highly linear RSS growth (R²={rss_r2:.2f}); "
            "capture a longer window to confirm.",
        )

    return ("none", 10, "No strong leak pattern in current capture window.")


def _check_resource_correlation(
    threads: MetricDelta,
    open_files: MetricDelta,
    connections: MetricDelta,
) -> tuple[bool, list[str]]:
    """Check whether resource metrics correlate with potential leak."""
    warnings: list[str] = []
    correlated = False

    if threads.growth > 0 and threads.increasing_ratio >= 0.6:
        warnings.append(
            f"Thread count growing (+{int(threads.growth)}, "
            f"trend {threads.increasing_ratio:.0%}) — possible thread leak."
        )
        correlated = True
    if open_files.growth > 0 and open_files.increasing_ratio >= 0.6:
        warnings.append(
            f"Open file descriptors growing (+{int(open_files.growth)}, "
            f"trend {open_files.increasing_ratio:.0%}) — possible FD leak."
        )
        correlated = True
    if connections.growth > 0 and connections.increasing_ratio >= 0.6:
        warnings.append(
            f"Network connections growing (+{int(connections.growth)}, "
            f"trend {connections.increasing_ratio:.0%}) — possible connection leak."
        )
        correlated = True

    return correlated, warnings


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

    confidence, score, diagnosis = _confidence_from_metrics(rss, uss, len(samples))
    duration = max(0.0, (len(samples) - 1) * interval_seconds)

    resource_correlated, resource_warnings = _check_resource_correlation(
        threads, open_files, connections,
    )

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
        resource_correlated=resource_correlated,
        resource_warnings=resource_warnings,
    )
