"""Tests for deep Python tracemalloc analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from thirtysecs.deep_python import run_deep_python_analysis


def test_run_deep_python_analysis_script_detects_growth(tmp_path: Path) -> None:
    script = tmp_path / "leaky_script.py"
    script.write_text(
        "\n".join(
            [
                "payload = []",
                "for _ in range(500):",
                "    payload.append(bytearray(2048))",
                "print(len(payload))",
            ]
        )
    )

    report = run_deep_python_analysis(
        script_path=str(script),
        script_args=[],
        top_lines=10,
        top_types=10,
        traceback_limit=10,
    )

    assert report.duration_seconds >= 0
    assert report.traced_peak_bytes >= 0
    assert len(report.top_lines) > 0
    assert any(item.size_diff > 0 for item in report.top_lines)
    assert len(report.top_types) > 0


def test_run_deep_python_analysis_requires_single_target() -> None:
    with pytest.raises(ValueError):
        run_deep_python_analysis(script_path="a.py", module_name="mod")
