"""Tests for memory collector enhancements."""

from __future__ import annotations

from unittest.mock import patch

from thirtysecs.collectors.memory import (
    _bytes_to_human,
    _parse_psi,
    collect_meminfo_details,
)


def test_bytes_to_human() -> None:
    assert _bytes_to_human(0) == "0.00 B"
    assert _bytes_to_human(1024) == "1.00 KB"
    assert _bytes_to_human(1048576) == "1.00 MB"
    assert _bytes_to_human(1073741824) == "1.00 GB"


def test_parse_psi_valid(tmp_path) -> None:
    psi_file = tmp_path / "memory"
    psi_file.write_text(
        "some avg10=1.50 avg60=2.00 avg300=0.50 total=12345\n"
        "full avg10=0.00 avg60=0.10 avg300=0.00 total=100\n"
    )
    result = _parse_psi(psi_file)
    assert "some" in result
    assert result["some"]["avg10"] == 1.50
    assert result["some"]["avg60"] == 2.00
    assert "full" in result
    assert result["full"]["total"] == 100.0


def test_parse_psi_empty(tmp_path) -> None:
    psi_file = tmp_path / "memory"
    psi_file.write_text("")
    result = _parse_psi(psi_file)
    assert result == {}


def test_parse_psi_missing(tmp_path) -> None:
    result = _parse_psi(tmp_path / "nonexistent")
    assert result == {}


def test_collect_meminfo_details_parses_fields() -> None:
    fake_meminfo = (
        "MemTotal:       16384000 kB\n"
        "MemFree:         8192000 kB\n"
        "Buffers:          512000 kB\n"
        "Cached:          2048000 kB\n"
        "Slab:             256000 kB\n"
        "SReclaimable:     128000 kB\n"
        "SUnreclaim:       128000 kB\n"
        "PageTables:        32000 kB\n"
        "KernelStack:       16000 kB\n"
        "HugePages_Total:       0\n"
    )
    from unittest.mock import mock_open

    with patch("builtins.open", mock_open(read_data=fake_meminfo)):
        result = collect_meminfo_details()

    assert "Buffers" in result
    assert result["Buffers"] == 512000 * 1024
    assert "Cached" in result
    assert "Slab" in result
    assert "PageTables" in result
    # MemTotal and MemFree are not in fields_of_interest
    assert "MemTotal" not in result
    assert "MemFree" not in result
