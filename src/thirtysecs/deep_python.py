"""Deep Python memory analysis using tracemalloc."""

from __future__ import annotations

import gc
import runpy
import sys
import time
import tracemalloc
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class LineGrowth:
    """Memory growth stat for one source line."""

    filename: str
    lineno: int
    size_diff: int
    count_diff: int
    traceback: list[str]


@dataclass
class TypeGrowth:
    """Object growth stat for one Python type."""

    type_name: str
    count_diff: int
    size_diff: int


@dataclass
class DeepPythonReport:
    """Result of tracemalloc-based deep analysis."""

    target: str
    args: list[str]
    duration_seconds: float
    traced_current_bytes: int
    traced_peak_bytes: int
    top_lines: list[LineGrowth]
    top_types: list[TypeGrowth]


def _capture_type_summary() -> tuple[dict[str, int], dict[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    sizes: dict[str, int] = defaultdict(int)
    for obj in gc.get_objects():
        obj_type = type(obj)
        type_name = f"{obj_type.__module__}.{obj_type.__name__}"
        counts[type_name] += 1
        try:
            sizes[type_name] += sys.getsizeof(obj)
        except TypeError:
            continue
    return dict(counts), dict(sizes)


def _diff_types(
    before_counts: dict[str, int],
    before_sizes: dict[str, int],
    after_counts: dict[str, int],
    after_sizes: dict[str, int],
    top_n: int,
) -> list[TypeGrowth]:
    all_types = set(before_counts) | set(after_counts) | set(before_sizes) | set(after_sizes)
    diffs: list[TypeGrowth] = []
    for type_name in all_types:
        count_diff = after_counts.get(type_name, 0) - before_counts.get(type_name, 0)
        size_diff = after_sizes.get(type_name, 0) - before_sizes.get(type_name, 0)
        if count_diff > 0 or size_diff > 0:
            diffs.append(
                TypeGrowth(type_name=type_name, count_diff=count_diff, size_diff=size_diff)
            )

    diffs.sort(key=lambda x: (x.size_diff, x.count_diff), reverse=True)
    return diffs[:top_n]


def _extract_line_growth(
    before_snapshot: tracemalloc.Snapshot,
    after_snapshot: tracemalloc.Snapshot,
    top_n: int,
) -> list[LineGrowth]:
    raw_stats = after_snapshot.compare_to(before_snapshot, "lineno")
    growth: list[LineGrowth] = []
    for stat in raw_stats:
        if stat.size_diff <= 0:
            continue
        frame = stat.traceback[0]
        traceback_lines = [f"{f.filename}:{f.lineno}" for f in stat.traceback]
        growth.append(
            LineGrowth(
                filename=frame.filename,
                lineno=frame.lineno,
                size_diff=stat.size_diff,
                count_diff=stat.count_diff,
                traceback=traceback_lines,
            )
        )
        if len(growth) >= top_n:
            break
    return growth


def run_deep_python_analysis(
    *,
    script_path: str | None = None,
    module_name: str | None = None,
    script_args: list[str] | None = None,
    top_lines: int = 20,
    top_types: int = 20,
    traceback_limit: int = 25,
) -> DeepPythonReport:
    """Run a Python target under tracemalloc and return growth report."""
    if bool(script_path) == bool(module_name):
        raise ValueError("Exactly one of script_path or module_name must be provided")

    if top_lines <= 0 or top_types <= 0 or traceback_limit <= 0:
        raise ValueError("top_lines, top_types, and traceback_limit must be > 0")

    args = script_args or []
    target = script_path or f"-m {module_name}"
    argv0 = script_path if script_path else module_name
    if argv0 is None:
        raise ValueError("Invalid target")

    old_argv = sys.argv[:]
    start = time.perf_counter()
    tracemalloc.start(traceback_limit)
    try:
        gc.collect()
        before_snapshot = tracemalloc.take_snapshot()
        before_counts, before_sizes = _capture_type_summary()

        sys.argv = [argv0, *args]
        try:
            if script_path:
                runpy.run_path(script_path, run_name="__main__")
            else:
                runpy.run_module(module_name, run_name="__main__", alter_sys=True)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code != 0:
                raise RuntimeError(f"Target exited with non-zero code: {code}") from exc

        gc.collect()
        after_snapshot = tracemalloc.take_snapshot()
        after_counts, after_sizes = _capture_type_summary()
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        sys.argv = old_argv

    duration = time.perf_counter() - start

    return DeepPythonReport(
        target=target,
        args=args,
        duration_seconds=duration,
        traced_current_bytes=current,
        traced_peak_bytes=peak,
        top_lines=_extract_line_growth(before_snapshot, after_snapshot, top_n=top_lines),
        top_types=_diff_types(
            before_counts,
            before_sizes,
            after_counts,
            after_sizes,
            top_n=top_types,
        ),
    )
