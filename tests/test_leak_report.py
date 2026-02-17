"""Tests for leak report analysis."""

from __future__ import annotations

import pytest

from thirtysecs.leak_report import (
    LeakSample,
    _check_resource_correlation,
    _linear_regression,
    _metric_delta,
    analyze_samples,
    sample_from_process_detail,
)


# ── helpers ──────────────────────────────────────────────────────────


def _make_sample(
    rss: int,
    uss: int | None = None,
    pss: int | None = None,
    threads: int = 10,
    open_files: int = 5,
    connections: int = 2,
) -> LeakSample:
    return LeakSample(
        timestamp="2026-02-15T00:00:00+00:00",
        rss=rss,
        uss=uss,
        pss=pss,
        threads=threads,
        open_files=open_files,
        connections=connections,
    )


MB = 1024 * 1024


# ── existing tests (preserved) ──────────────────────────────────────


def test_analyze_samples_high_confidence_when_rss_uss_grow() -> None:
    samples = [
        LeakSample(
            timestamp="2026-02-15T00:00:00+00:00",
            rss=100 * MB,
            uss=80 * MB,
            pss=90 * MB,
            threads=10,
            open_files=5,
            connections=2,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:02+00:00",
            rss=115 * MB,
            uss=92 * MB,
            pss=101 * MB,
            threads=11,
            open_files=5,
            connections=2,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:04+00:00",
            rss=130 * MB,
            uss=105 * MB,
            pss=114 * MB,
            threads=12,
            open_files=6,
            connections=2,
        ),
    ]

    analysis = analyze_samples(samples, interval_seconds=2.0)
    # With only 3 samples the improved algorithm caps confidence at medium
    # (short_window penalty) — this is intentional to reduce false positives.
    assert analysis.confidence in ("medium", "high")
    assert analysis.score >= 60
    assert analysis.rss.growth > 0
    assert analysis.uss is not None
    assert analysis.uss.growth > 0
    assert analysis.sample_count == 3
    assert analysis.duration_seconds == 4.0


def test_analyze_samples_none_confidence_when_flat() -> None:
    samples = [
        LeakSample(
            timestamp="2026-02-15T00:00:00+00:00",
            rss=200 * MB,
            uss=None,
            pss=None,
            threads=20,
            open_files=9,
            connections=4,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:05+00:00",
            rss=201 * MB,
            uss=None,
            pss=None,
            threads=20,
            open_files=9,
            connections=4,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:10+00:00",
            rss=200 * MB,
            uss=None,
            pss=None,
            threads=20,
            open_files=9,
            connections=4,
        ),
    ]

    analysis = analyze_samples(samples, interval_seconds=5.0)
    assert analysis.confidence == "none"
    assert analysis.score == 10
    assert analysis.uss is None
    assert analysis.pss is None


# ── linear regression ────────────────────────────────────────────────


def test_linear_regression_perfect_upward() -> None:
    slope, r2 = _linear_regression([1.0, 2.0, 3.0, 4.0, 5.0])
    assert slope == pytest.approx(1.0)
    assert r2 == pytest.approx(1.0)


def test_linear_regression_flat() -> None:
    slope, r2 = _linear_regression([5.0, 5.0, 5.0, 5.0])
    assert slope == 0.0
    assert r2 == 0.0


def test_linear_regression_single_value() -> None:
    slope, r2 = _linear_regression([42.0])
    assert slope == 0.0
    assert r2 == 0.0


def test_linear_regression_two_values() -> None:
    slope, r2 = _linear_regression([10.0, 20.0])
    assert slope == pytest.approx(10.0)
    assert r2 == pytest.approx(1.0)


def test_linear_regression_noisy() -> None:
    # Not a perfect line — r² should be < 1
    slope, r2 = _linear_regression([1.0, 3.0, 2.0, 4.0, 3.5])
    assert slope > 0
    assert 0 < r2 < 1.0


# ── metric delta ─────────────────────────────────────────────────────


def test_metric_delta_includes_slope_and_r_squared() -> None:
    delta = _metric_delta([100.0, 200.0, 300.0])
    assert delta.slope > 0
    assert delta.r_squared == pytest.approx(1.0)
    assert delta.growth == 200.0
    assert delta.growth_percent == pytest.approx(200.0)


# ── sample_from_process_detail ───────────────────────────────────────


def test_sample_from_process_detail_full() -> None:
    detail = {
        "memory": {"rss": 1024, "uss": 512, "pss": 768},
        "threads": {"count": 4},
        "open_files": {"count": 10},
        "connections": {"count": 3},
    }
    sample = sample_from_process_detail(detail)
    assert sample.rss == 1024
    assert sample.uss == 512
    assert sample.pss == 768
    assert sample.threads == 4
    assert sample.open_files == 10
    assert sample.connections == 3


def test_sample_from_process_detail_missing_optional() -> None:
    detail = {
        "memory": {"rss": 2048},
        "threads": {},
        "open_files": {},
        "connections": {},
    }
    sample = sample_from_process_detail(detail)
    assert sample.rss == 2048
    assert sample.uss is None
    assert sample.pss is None
    assert sample.threads == 0


# ── edge cases ───────────────────────────────────────────────────────


def test_analyze_single_sample() -> None:
    samples = [_make_sample(rss=100 * MB)]
    analysis = analyze_samples(samples, interval_seconds=1.0)
    assert analysis.confidence == "none"
    assert analysis.sample_count == 1
    assert analysis.duration_seconds == 0.0


def test_analyze_two_samples_limits_confidence() -> None:
    """Two samples with dramatic growth should not trigger high confidence."""
    samples = [
        _make_sample(rss=100 * MB, uss=80 * MB),
        _make_sample(rss=200 * MB, uss=160 * MB),
    ]
    analysis = analyze_samples(samples, interval_seconds=1.0)
    # The new logic caps two-sample analyses at "low" confidence
    assert analysis.confidence == "low"
    assert analysis.score <= 40


def test_analyze_oscillating_pattern_no_false_positive() -> None:
    """Memory that oscillates should not be flagged as a leak."""
    rss_values = [100, 120, 100, 120, 100, 120, 100, 120]
    samples = [_make_sample(rss=v * MB) for v in rss_values]
    analysis = analyze_samples(samples, interval_seconds=1.0)
    assert analysis.confidence == "none"


def test_analyze_slow_linear_leak_detected() -> None:
    """A slow but perfectly linear leak should get at least low confidence."""
    # 1% growth per sample over 20 samples = 20% total growth
    base = 100 * MB
    samples = [_make_sample(rss=base + i * MB) for i in range(20)]
    analysis = analyze_samples(samples, interval_seconds=1.0)
    assert analysis.confidence in ("low", "medium", "high")
    assert analysis.score > 10
    assert analysis.rss.r_squared > 0.9


def test_analyze_empty_samples_raises() -> None:
    with pytest.raises(ValueError, match="samples cannot be empty"):
        analyze_samples([], interval_seconds=1.0)


# ── resource correlation ─────────────────────────────────────────────


def test_resource_correlation_thread_leak() -> None:
    threads = _metric_delta([10.0, 11.0, 12.0, 13.0, 14.0])
    open_files = _metric_delta([5.0, 5.0, 5.0, 5.0, 5.0])
    connections = _metric_delta([2.0, 2.0, 2.0, 2.0, 2.0])
    correlated, warnings = _check_resource_correlation(threads, open_files, connections)
    assert correlated is True
    assert any("thread" in w.lower() for w in warnings)


def test_resource_correlation_nothing() -> None:
    flat = _metric_delta([5.0, 5.0, 5.0, 5.0, 5.0])
    correlated, warnings = _check_resource_correlation(flat, flat, flat)
    assert correlated is False
    assert warnings == []


def test_analysis_includes_resource_warnings() -> None:
    """Verify the full analysis propagates resource warnings."""
    samples = [
        _make_sample(rss=100 * MB, threads=10, open_files=5, connections=2),
        _make_sample(rss=120 * MB, threads=15, open_files=10, connections=5),
        _make_sample(rss=140 * MB, threads=20, open_files=15, connections=8),
        _make_sample(rss=160 * MB, threads=25, open_files=20, connections=11),
        _make_sample(rss=180 * MB, threads=30, open_files=25, connections=14),
    ]
    analysis = analyze_samples(samples, interval_seconds=1.0)
    assert analysis.resource_correlated is True
    assert len(analysis.resource_warnings) >= 1
