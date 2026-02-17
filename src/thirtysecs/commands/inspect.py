"""Process inspect command handler."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspect a specific process in detail."""
    from ..collectors.process import get_process_detail

    pid = args.pid
    detail = get_process_detail(pid)

    if detail is None:
        sys.stderr.write(f"Error: Process {pid} not found\n")
        return 1

    if "error" in detail and detail.get("error") == "Access denied":
        sys.stderr.write(f"Error: Access denied for process {pid}\n")
        return 1

    if args.format == "json":
        sys.stdout.write(json.dumps(detail, indent=2, default=str) + "\n")
    else:
        _print_process_detail(detail)

    return 0


def _print_process_detail(detail: dict[str, Any]) -> None:
    """Print process detail in human-readable format."""
    lines = [
        "=" * 60,
        f"  Process Detail - PID {detail['pid']}",
        "=" * 60,
        "",
        "BASIC INFO",
        f"  Name:        {detail.get('name', 'N/A')}",
        f"  Status:      {detail.get('status', 'N/A')}",
        f"  User:        {detail.get('username', 'N/A')}",
        f"  Created:     {detail.get('create_time', 'N/A')}",
        f"  Command:     {detail.get('cmdline', 'N/A')[:80]}",
    ]

    if detail.get("cwd"):
        lines.append(f"  Working Dir: {detail['cwd']}")

    if detail.get("parent"):
        lines.append(f"  Parent:      {detail['parent']['name']} (PID {detail['parent']['pid']})")

    mem = detail.get("memory", {})
    if "error" not in mem:
        lines.extend(
            [
                "",
                "MEMORY",
                f"  RSS:         {mem.get('rss_human', 'N/A')} ({mem.get('percent', 0):.1f}%)",
                f"  VMS:         {mem.get('vms_human', 'N/A')}",
            ]
        )
        if mem.get("uss_human"):
            lines.append(f"  USS:         {mem.get('uss_human', 'N/A')} (unique to this process)")
        if mem.get("pss_human"):
            lines.append(f"  PSS:         {mem.get('pss_human', 'N/A')} (proportional share)")

    cpu = detail.get("cpu", {})
    threads = detail.get("threads", {})
    lines.extend(
        [
            "",
            "CPU & THREADS",
            f"  CPU:         {cpu.get('percent', 0):.1f}%",
            f"  Threads:     {threads.get('count', cpu.get('num_threads', 0))}",
        ]
    )

    open_files = detail.get("open_files", {})
    if open_files.get("count", 0) > 0:
        lines.extend(["", f"OPEN FILES ({open_files['count']} total)"])
        for f in open_files.get("files", [])[:10]:
            lines.append(f"  - {f}")
        if open_files["count"] > 10:
            lines.append(f"  ... and {open_files['count'] - 10} more")

    conns = detail.get("connections", {})
    if conns.get("count", 0) > 0:
        lines.extend(["", f"NETWORK CONNECTIONS ({conns['count']} total)"])
        for c in conns.get("details", [])[:10]:
            laddr = c.get("laddr", "N/A")
            raddr = c.get("raddr", "N/A") or "*"
            status = c.get("status", "")
            lines.append(f"  - {laddr} -> {raddr} ({status})")

    children = detail.get("children", [])
    if children:
        lines.extend(["", f"CHILD PROCESSES ({len(children)})"])
        for c in children[:10]:
            lines.append(f"  - PID {c['pid']}: {c['name']}")

    lines.append("")
    sys.stdout.write("\n".join(lines) + "\n")
