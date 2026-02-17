"""Tests for OOM killer event detection."""

from __future__ import annotations

from thirtysecs.oom import OomEvent, _parse_oom_events


def test_parse_full_oom_line() -> None:
    lines = [
        "[12345.678] Out of memory: Killed process 9876 (myapp) "
        "total-vm:1234560kB, anon-rss:567890kB, file-rss:12345kB"
    ]
    events = _parse_oom_events(lines, source="dmesg")
    assert len(events) == 1
    ev = events[0]
    assert ev.pid == 9876
    assert ev.name == "myapp"
    assert ev.total_vm_kb == 1234560
    assert ev.anon_rss_kb == 567890
    assert ev.file_rss_kb == 12345
    assert ev.source == "dmesg"


def test_parse_oom_summary_line() -> None:
    lines = [
        "oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),"
        "cpuset=/,mems_allowed=0,oom_memcg=/user.slice,"
        "task_memcg=/user.slice/user-1000.slice,"
        "task=python3 pid=42 uid=1000"
    ]
    events = _parse_oom_events(lines, source="journal")
    assert len(events) == 1
    assert events[0].pid == 42
    assert events[0].name == "python3"
    assert events[0].memcg is not None


def test_parse_short_oom_line() -> None:
    lines = ["Killed process 555 (leaky-svc)"]
    events = _parse_oom_events(lines, source="dmesg")
    assert len(events) == 1
    assert events[0].pid == 555
    assert events[0].name == "leaky-svc"
    assert events[0].total_vm_kb is None


def test_parse_no_oom_lines() -> None:
    lines = ["Some random kernel message", "Another log line"]
    events = _parse_oom_events(lines, source="dmesg")
    assert events == []


def test_parse_mixed_lines() -> None:
    lines = [
        "noise",
        "Out of memory: Killed process 100 (a) total-vm:1000kB, anon-rss:500kB, file-rss:100kB",
        "more noise",
        "Killed process 200 (b)",
    ]
    events = _parse_oom_events(lines, source="journal")
    assert len(events) == 2
    assert {ev.pid for ev in events} == {100, 200}
