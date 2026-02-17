"""Leak analysis command handlers."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from dataclasses import asdict
from typing import Any

from ..core import collect_snapshot
from ..deep_python import DeepPythonReport, run_deep_python_analysis
from ..leak_report import LeakAnalysis, analyze_samples, sample_from_process_detail


def _output(data: str, output_file: str | None = None) -> None:
    """Write output to stdout or file."""
    if output_file:
        mode = "a" if os.path.exists(output_file) else "w"
        with open(output_file, mode) as f:
            f.write(data + "\n")
    else:
        sys.stdout.write(data + "\n")
        sys.stdout.flush()


def _bytes_to_human(n: float) -> str:
    value = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(value) < 1024.0:
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{value:.2f} PB"


def _metric_row(label: str, start: str, end: str, growth: str, pct: str, trend: str) -> str:
    return f"| {label:<11} | {start:>13} | {end:>13} | {growth:>13} | {pct:>9} | {trend:>8} |"


def _format_leak_table(
    detail: dict[str, Any],
    analysis: LeakAnalysis,
    interval: float,
) -> str:
    lines: list[str] = [
        "=" * 88,
        f"  Memory Leak Report - PID {detail['pid']} ({detail.get('name', 'N/A')})",
        "=" * 88,
        f"Command: {detail.get('cmdline', 'N/A')[:120]}",
        f"Samples: {analysis.sample_count} | Interval: {interval:.2f}s | Duration: {analysis.duration_seconds:.2f}s",
        f"Leak Score: {analysis.score}/100 ({analysis.confidence.upper()})",
        f"Diagnosis: {analysis.diagnosis}",
        "",
        "+-------------+---------------+---------------+---------------+-----------+----------+",
        "| Metric      | Start         | End           | Growth        | Growth %  | Trend Up |",
        "+-------------+---------------+---------------+---------------+-----------+----------+",
    ]

    rss = analysis.rss
    rss_pct = f"{rss.growth_percent:.2f}%" if rss.growth_percent is not None else "N/A"
    lines.append(
        _metric_row(
            "RSS",
            _bytes_to_human(rss.start),
            _bytes_to_human(rss.end),
            _bytes_to_human(rss.growth),
            rss_pct,
            f"{rss.increasing_ratio:.0%}",
        )
    )

    if analysis.uss:
        uss = analysis.uss
        uss_pct = f"{uss.growth_percent:.2f}%" if uss.growth_percent is not None else "N/A"
        lines.append(
            _metric_row(
                "USS",
                _bytes_to_human(uss.start),
                _bytes_to_human(uss.end),
                _bytes_to_human(uss.growth),
                uss_pct,
                f"{uss.increasing_ratio:.0%}",
            )
        )

    if analysis.pss:
        pss = analysis.pss
        pss_pct = f"{pss.growth_percent:.2f}%" if pss.growth_percent is not None else "N/A"
        lines.append(
            _metric_row(
                "PSS",
                _bytes_to_human(pss.start),
                _bytes_to_human(pss.end),
                _bytes_to_human(pss.growth),
                pss_pct,
                f"{pss.increasing_ratio:.0%}",
            )
        )

    threads = analysis.threads
    open_files = analysis.open_files
    connections = analysis.connections
    lines.append(
        _metric_row(
            "Threads",
            f"{int(threads.start)}",
            f"{int(threads.end)}",
            f"{int(threads.growth):+d}",
            "N/A",
            f"{threads.increasing_ratio:.0%}",
        )
    )
    lines.append(
        _metric_row(
            "Open files",
            f"{int(open_files.start)}",
            f"{int(open_files.end)}",
            f"{int(open_files.growth):+d}",
            "N/A",
            f"{open_files.increasing_ratio:.0%}",
        )
    )
    lines.append(
        _metric_row(
            "Connections",
            f"{int(connections.start)}",
            f"{int(connections.end)}",
            f"{int(connections.growth):+d}",
            "N/A",
            f"{connections.increasing_ratio:.0%}",
        )
    )
    lines.extend(
        [
            "+-------------+---------------+---------------+---------------+-----------+----------+",
            "",
        ]
    )

    # R² and slope summary
    lines.append(
        f"Linear fit: RSS slope={_bytes_to_human(analysis.rss.slope)}/sample, "
        f"R²={analysis.rss.r_squared:.2f}"
    )
    if analysis.uss:
        lines.append(
            f"            USS slope={_bytes_to_human(analysis.uss.slope)}/sample, "
            f"R²={analysis.uss.r_squared:.2f}"
        )
    lines.append("")

    # Resource correlation warnings
    if analysis.resource_warnings:
        lines.append("Resource warnings:")
        for warning in analysis.resource_warnings:
            lines.append(f"  - {warning}")
        lines.append("")

    return "\n".join(lines)


def _format_leak_top_table(results: list[dict[str, Any]], interval: float, count: int) -> str:
    lines: list[str] = [
        "=" * 112,
        "  Leak Top Report - Ranked Memory Leak Candidates",
        "=" * 112,
        f"Window: {count} samples x {interval:.2f}s = {(count - 1) * interval:.2f}s",
        "",
        "+------+--------+----------------------+---------+-----------+----------+----------+",
        "| Rank | PID    | Name                 | Score   | Confidence| RSS %    | Trend Up |",
        "+------+--------+----------------------+---------+-----------+----------+----------+",
    ]

    for idx, result in enumerate(results, start=1):
        analysis: LeakAnalysis = result["analysis"]
        rss_pct = analysis.rss.growth_percent if analysis.rss.growth_percent is not None else 0.0
        lines.append(
            f"| {idx:>4} | {result['pid']:>6} | {result['name'][:20]:<20} |"
            f" {analysis.score:>3}/100 | {analysis.confidence.upper():<9} |"
            f" {rss_pct:>7.2f}% | {analysis.rss.increasing_ratio:>7.0%} |"
        )

    lines.extend(
        [
            "+------+--------+----------------------+---------+-----------+----------+----------+",
            "",
            "Top diagnosis:",
        ]
    )
    for idx, result in enumerate(results[:3], start=1):
        analysis = result["analysis"]
        lines.append(f"{idx}. PID {result['pid']} ({result['name']}): {analysis.diagnosis}")
    lines.append("")
    return "\n".join(lines)


def _format_deep_python_table(report: DeepPythonReport) -> str:
    lines: list[str] = [
        "=" * 112,
        "  Python Deep Leak Report (tracemalloc)",
        "=" * 112,
        f"Target: {report.target}",
        f"Args: {' '.join(report.args) if report.args else '(none)'}",
        f"Duration: {report.duration_seconds:.2f}s | Traced current: {_bytes_to_human(report.traced_current_bytes)} | Traced peak: {_bytes_to_human(report.traced_peak_bytes)}",
        "",
        "Top Growing Lines:",
        "+------+-----------------------------------------------+----------------+-----------+",
        "| Rank | File:Line                                     | Size +         | Count +   |",
        "+------+-----------------------------------------------+----------------+-----------+",
    ]

    if report.top_lines:
        for idx, item in enumerate(report.top_lines, start=1):
            file_line = f"{os.path.basename(item.filename)}:{item.lineno}"
            lines.append(
                f"| {idx:>4} | {file_line[:45]:<45} | {_bytes_to_human(item.size_diff):>14} | {item.count_diff:>9} |"
            )
    else:
        lines.append(
            "|    - | (no positive line-level growth captured)       |              - |         - |"
        )
    lines.extend(
        [
            "+------+-----------------------------------------------+----------------+-----------+",
            "",
            "Top Growing Object Types:",
            "+------+-----------------------------------------------+----------------+-----------+",
            "| Rank | Type                                          | Size +         | Count +   |",
            "+------+-----------------------------------------------+----------------+-----------+",
        ]
    )

    if report.top_types:
        for idx, item in enumerate(report.top_types, start=1):
            lines.append(
                f"| {idx:>4} | {item.type_name[:45]:<45} | {_bytes_to_human(item.size_diff):>14} | {item.count_diff:>9} |"
            )
    else:
        lines.append(
            "|    - | (no positive type growth captured)             |              - |         - |"
        )
    lines.extend(
        [
            "+------+-----------------------------------------------+----------------+-----------+",
            "",
            "Note: tracemalloc tracks Python allocations after tracer start; native allocations may be underrepresented.",
            "",
        ]
    )
    return "\n".join(lines)


def _cmd_leak_deep_python(args: argparse.Namespace) -> int:
    """Run deep Python tracemalloc analysis for a script/module."""
    if not args.script and not args.module:
        sys.stderr.write("Error: --deep-python requires either --script or --module\n")
        return 2
    if args.script and args.module:
        sys.stderr.write("Error: choose one target: --script or --module\n")
        return 2

    try:
        script_args = shlex.split(args.script_args) if args.script_args else []
    except ValueError as exc:
        sys.stderr.write(f"Error: invalid --script-args: {exc}\n")
        return 2

    try:
        report = run_deep_python_analysis(
            script_path=args.script,
            module_name=args.module,
            script_args=script_args,
            top_lines=args.top_lines,
            top_types=args.top_types,
            traceback_limit=args.traceback_limit,
        )
    except (ValueError, RuntimeError, FileNotFoundError, ImportError) as exc:
        sys.stderr.write(f"Error: deep python analysis failed: {exc}\n")
        return 1

    if args.format == "json":
        _output(json.dumps(asdict(report), indent=2), args.output)
    else:
        _output(_format_deep_python_table(report), args.output)
    return 0


def _cmd_leak_top(args: argparse.Namespace) -> int:
    """Rank top memory leak candidates from memory-heavy processes."""
    from ..collectors.process import get_process_detail

    interval = float(args.interval)
    count = int(args.count)
    limit = int(args.limit)

    if interval <= 0:
        sys.stderr.write("Error: --interval must be > 0\n")
        return 2
    if count < 2:
        sys.stderr.write("Error: --count must be >= 2\n")
        return 2
    if limit <= 0:
        sys.stderr.write("Error: --limit must be >= 1\n")
        return 2

    snapshot = collect_snapshot(include_processes=True, include_network=False, include_disk=False)
    processes = snapshot.get("processes", {})
    top_by_memory = processes.get("top_by_memory", [])
    if not top_by_memory:
        sys.stderr.write("Error: could not retrieve process list for top leak analysis\n")
        return 1

    candidates = top_by_memory[:limit]
    pids = [int(p["pid"]) for p in candidates]
    samples_by_pid: dict[int, list[Any]] = {pid: [] for pid in pids}
    details_by_pid: dict[int, dict[str, Any]] = {}
    dead_pids: set[int] = set()

    for idx in range(count):
        for pid in pids:
            if pid in dead_pids:
                continue
            detail = get_process_detail(pid)
            if detail is None or "error" in detail:
                dead_pids.add(pid)
                continue
            samples_by_pid[pid].append(sample_from_process_detail(detail))
            details_by_pid[pid] = detail

        if idx < count - 1:
            time.sleep(interval)

    results: list[dict[str, Any]] = []
    for pid in pids:
        samples = samples_by_pid.get(pid, [])
        detail = details_by_pid.get(pid)
        if detail is None or len(samples) < 2:
            continue
        analysis = analyze_samples(samples, interval_seconds=interval)
        results.append(
            {
                "pid": pid,
                "name": detail.get("name", "N/A"),
                "cmdline": detail.get("cmdline", "N/A"),
                "analysis": analysis,
                "sample_count": len(samples),
            }
        )

    if not results:
        sys.stderr.write("Error: no analyzable processes remained during sampling\n")
        return 1

    results.sort(
        key=lambda r: (
            r["analysis"].score,
            r["analysis"].rss.growth_percent or 0.0,
            r["analysis"].rss.increasing_ratio,
        ),
        reverse=True,
    )

    if args.format == "json":
        payload = {
            "window": {
                "interval_seconds": interval,
                "requested_count": count,
                "requested_limit": limit,
            },
            "results": [
                {
                    "rank": idx + 1,
                    "pid": result["pid"],
                    "name": result["name"],
                    "cmdline": result["cmdline"],
                    "sample_count": result["sample_count"],
                    "analysis": {
                        "sample_count": result["analysis"].sample_count,
                        "duration_seconds": result["analysis"].duration_seconds,
                        "confidence": result["analysis"].confidence,
                        "score": result["analysis"].score,
                        "diagnosis": result["analysis"].diagnosis,
                        "rss": result["analysis"].rss.__dict__,
                        "uss": result["analysis"].uss.__dict__ if result["analysis"].uss else None,
                        "pss": result["analysis"].pss.__dict__ if result["analysis"].pss else None,
                        "threads": result["analysis"].threads.__dict__,
                        "open_files": result["analysis"].open_files.__dict__,
                        "connections": result["analysis"].connections.__dict__,
                    },
                }
                for idx, result in enumerate(results)
            ],
        }
        _output(json.dumps(payload, indent=2), args.output)
    else:
        _output(_format_leak_top_table(results, interval, count), args.output)

    return 0


def cmd_leak(args: argparse.Namespace) -> int:
    """Capture process samples and print a leak analysis report."""
    from ..collectors.process import get_process_detail

    if args.deep_python:
        return _cmd_leak_deep_python(args)

    interval = float(args.interval)
    if interval <= 0:
        sys.stderr.write("Error: --interval must be > 0\n")
        return 2
    if args.count < 2:
        sys.stderr.write("Error: --count must be >= 2\n")
        return 2

    if str(args.pid).lower() == "top":
        return _cmd_leak_top(args)

    if args.pid is None:
        sys.stderr.write("Error: pid is required, or enable --deep-python mode\n")
        return 2

    try:
        pid = int(args.pid)
    except ValueError:
        sys.stderr.write("Error: pid must be an integer, or use `30secs leak top`\n")
        return 2

    samples = []
    last_detail: dict[str, Any] | None = None

    for idx in range(args.count):
        detail = get_process_detail(pid)
        if detail is None:
            sys.stderr.write(f"Error: Process {pid} not found during sampling (sample {idx + 1})\n")
            return 1
        if "error" in detail:
            sys.stderr.write(f"Error: {detail['error']} for process {pid}\n")
            return 1
        samples.append(sample_from_process_detail(detail))
        last_detail = detail

        if idx < args.count - 1:
            time.sleep(interval)

    if last_detail is None:
        sys.stderr.write("Error: Failed to collect process detail\n")
        return 1

    analysis = analyze_samples(samples, interval)
    if args.format == "json":
        payload = {
            "pid": last_detail["pid"],
            "name": last_detail.get("name"),
            "cmdline": last_detail.get("cmdline"),
            "analysis": {
                "sample_count": analysis.sample_count,
                "duration_seconds": analysis.duration_seconds,
                "confidence": analysis.confidence,
                "score": analysis.score,
                "diagnosis": analysis.diagnosis,
                "rss": analysis.rss.__dict__,
                "uss": analysis.uss.__dict__ if analysis.uss else None,
                "pss": analysis.pss.__dict__ if analysis.pss else None,
                "threads": analysis.threads.__dict__,
                "open_files": analysis.open_files.__dict__,
                "connections": analysis.connections.__dict__,
            },
            "samples": [s.__dict__ for s in samples],
        }
        _output(json.dumps(payload, indent=2), args.output)
    else:
        _output(_format_leak_table(last_detail, analysis, interval), args.output)

    return 0


def add_leak_parser(subparsers: Any) -> None:
    """Register `leak` subcommand parser."""
    examples = (
        "Examples:\n"
        "  30secs leak 12345 -i 2 -n 30           # analyze PID 12345 (30 samples, 2s apart)\n"
        "  30secs leak 12345 -f json -o leak.json  # save leak report as JSON\n"
        "  30secs leak top -i 1 -n 20 -l 5         # rank top 5 leakiest processes\n"
        '  30secs leak --deep-python --script app.py --script-args "--mode stress"\n'
        '  30secs leak --deep-python --module myservice.main --script-args "--port 8080"\n'
        "\n"
        "Understanding the output:\n"
        "  Score    0-100 leak likelihood (higher = more likely leaking)\n"
        "  R²       Linear fit quality (1.0 = perfectly linear growth)\n"
        "  Slope    Memory growth rate per sample\n"
        "  Trend Up Fraction of consecutive samples that increased\n"
    )
    p_leak = subparsers.add_parser(
        "leak",
        help="Analyze memory leak trend for a specific process, or rank top candidates",
        description=(
            "Memory leak analysis commands:\n"
            "- PID mode:      sample one process and compute a leak score with\n"
            "                  linear regression (slope, R²), trend ratio, and\n"
            "                  resource correlation (threads, FDs, connections)\n"
            "- top mode:      rank the N heaviest processes by leak score\n"
            "- --deep-python: tracemalloc-based line/type growth report\n"
            "\n"
            "The report also includes smaps_rollup data and page fault\n"
            "counters when available (Linux)."
        ),
        epilog=examples,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_leak.add_argument(
        "pid",
        nargs="?",
        type=str,
        default=None,
        help="Process ID to analyze, or `top` for ranked candidate scan",
    )
    p_leak.add_argument(
        "--interval",
        "-i",
        type=float,
        default=2.0,
        help="Sampling interval in seconds (default: 2.0)",
    )
    p_leak.add_argument(
        "--count",
        "-n",
        type=int,
        default=30,
        help="Number of samples (default: 30)",
    )
    p_leak.add_argument(
        "--limit",
        "-l",
        type=int,
        default=5,
        help="For `leak top`: number of candidate processes to rank (default: 5)",
    )
    p_leak.add_argument(
        "--format",
        "-f",
        choices=["table", "json"],
        default="table",
        help="Report format (default: table)",
    )
    p_leak.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file (default: stdout)",
    )
    p_leak.add_argument(
        "--deep-python",
        action="store_true",
        help="Run Python deep analysis with tracemalloc (requires --script or --module)",
    )
    p_leak.add_argument(
        "--script",
        type=str,
        default=None,
        help="Python script path to run for deep analysis",
    )
    p_leak.add_argument(
        "--module",
        type=str,
        default=None,
        help="Python module name to run for deep analysis (e.g., mypkg.app)",
    )
    p_leak.add_argument(
        "--script-args",
        type=str,
        default="",
        help='Arguments for --script/--module as one quoted string, e.g. --script-args "--foo 1"',
    )
    p_leak.add_argument(
        "--top-lines",
        type=int,
        default=15,
        help="For --deep-python: number of top growing lines (default: 15)",
    )
    p_leak.add_argument(
        "--top-types",
        type=int,
        default=15,
        help="For --deep-python: number of top growing object types (default: 15)",
    )
    p_leak.add_argument(
        "--traceback-limit",
        type=int,
        default=25,
        help="For --deep-python: tracemalloc traceback depth (default: 25)",
    )
    p_leak.set_defaults(func=cmd_leak)
