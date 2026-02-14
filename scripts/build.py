#!/usr/bin/env python3
"""Build standalone binary for 30secs."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def build_pyinstaller() -> None:
    """Build standalone binary using PyInstaller."""
    entry_point = ROOT / "scripts" / "entrypoint.py"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "30secs",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
        "--clean",
        str(entry_point),
    ]

    subprocess.run(cmd, check=True, cwd=ROOT)
    print(f"\n✅ Binary built: {ROOT / 'dist' / '30secs'}")


if __name__ == "__main__":
    build_pyinstaller()
