"""Tests for leak report analysis."""

from __future__ import annotations

from thirtysecs.leak_report import LeakSample, analyze_samples


def test_analyze_samples_high_confidence_when_rss_uss_grow() -> None:
    samples = [
        LeakSample(
            timestamp="2026-02-15T00:00:00+00:00",
            rss=100 * 1024 * 1024,
            uss=80 * 1024 * 1024,
            pss=90 * 1024 * 1024,
            threads=10,
            open_files=5,
            connections=2,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:02+00:00",
            rss=115 * 1024 * 1024,
            uss=92 * 1024 * 1024,
            pss=101 * 1024 * 1024,
            threads=11,
            open_files=5,
            connections=2,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:04+00:00",
            rss=130 * 1024 * 1024,
            uss=105 * 1024 * 1024,
            pss=114 * 1024 * 1024,
            threads=12,
            open_files=6,
            connections=2,
        ),
    ]

    analysis = analyze_samples(samples, interval_seconds=2.0)
    assert analysis.confidence == "high"
    assert analysis.score >= 80
    assert analysis.rss.growth > 0
    assert analysis.uss is not None
    assert analysis.uss.growth > 0
    assert analysis.sample_count == 3
    assert analysis.duration_seconds == 4.0


def test_analyze_samples_none_confidence_when_flat() -> None:
    samples = [
        LeakSample(
            timestamp="2026-02-15T00:00:00+00:00",
            rss=200 * 1024 * 1024,
            uss=None,
            pss=None,
            threads=20,
            open_files=9,
            connections=4,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:05+00:00",
            rss=201 * 1024 * 1024,
            uss=None,
            pss=None,
            threads=20,
            open_files=9,
            connections=4,
        ),
        LeakSample(
            timestamp="2026-02-15T00:00:10+00:00",
            rss=200 * 1024 * 1024,
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
