#!/usr/bin/env python3
"""Scan a Windows drive or directory and report large folders/files.

The script is read-only: it never deletes or modifies scanned files.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import shutil
import time
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

REPARSE_POINT_ATTRIBUTE = 0x400


def format_bytes(size: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def is_reparse_point(stat_result: os.stat_result) -> bool:
    attributes = getattr(stat_result, "st_file_attributes", 0)
    return bool(attributes & REPARSE_POINT_ATTRIBUTE)


def relative_child(path: Path, parent: Path) -> str | None:
    """Return the first component below parent, or None if path is outside it."""
    try:
        relative = path.relative_to(parent)
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else path.name


def existing_breakdown_roots(scan_root: Path) -> dict[str, Path]:
    home = Path.home()
    drive_root = Path(scan_root.anchor) if scan_root.anchor else scan_root
    candidates = {
        "scan_root": scan_root,
        "user_profile": home,
        "appdata_local": home / "AppData" / "Local",
        "appdata_roaming": home / "AppData" / "Roaming",
        "program_files": drive_root / "Program Files",
        "program_files_x86": drive_root / "Program Files (x86)",
        "program_data": drive_root / "ProgramData",
        "windows": drive_root / "Windows",
    }
    return {name: path.resolve() for name, path in candidates.items() if path.exists()}


def scan(root: Path, output: Path, top_files: int, time_limit: int) -> dict:
    root = root.resolve()
    breakdown_roots = existing_breakdown_roots(root)
    aggregates: dict[str, DefaultDict[str, int]] = {
        name: defaultdict(int) for name in breakdown_roots
    }
    largest: list[tuple[int, str]] = []
    stack = [root]
    started = time.time()
    files_seen = 0
    errors = 0
    skipped_reparse_points = 0
    timed_out = False

    while stack:
        if time.time() - started > time_limit:
            timed_out = True
            break

        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        stat_result = entry.stat(follow_symlinks=False)
                        if is_reparse_point(stat_result):
                            skipped_reparse_points += 1
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue

                        size = stat_result.st_size
                        path = Path(entry.path).resolve()
                        files_seen += 1

                        for name, breakdown_root in breakdown_roots.items():
                            child = relative_child(path, breakdown_root)
                            if child is not None:
                                aggregates[name][child] += size

                        item = (size, str(path))
                        if len(largest) < top_files:
                            heapq.heappush(largest, item)
                        elif size > largest[0][0]:
                            heapq.heapreplace(largest, item)
                    except (OSError, PermissionError):
                        errors += 1
        except (OSError, PermissionError):
            errors += 1

    disk = shutil.disk_usage(root)
    report = {
        "scan_root": str(root),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "duration_seconds": round(time.time() - started, 2),
        "timed_out": timed_out,
        "files_seen": files_seen,
        "errors": errors,
        "skipped_reparse_points": skipped_reparse_points,
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
        },
        "breakdowns": {
            name: [
                {"name": child, "size_bytes": size}
                for child, size in sorted(values.items(), key=lambda item: item[1], reverse=True)
            ]
            for name, values in aggregates.items()
        },
        "largest_files": [
            {"path": path, "size_bytes": size}
            for size, path in sorted(largest, reverse=True)
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    default_root = f"{os.environ.get('SystemDrive', 'C:')}\\" if os.name == "nt" else str(Path.home())
    parser = argparse.ArgumentParser(description="Find large files and folders without changing them.")
    parser.add_argument("--root", default=default_root, help="Drive or directory to scan (default: system drive).")
    parser.add_argument("--output", default="storage_scan_report.json", help="JSON report path.")
    parser.add_argument("--top-files", type=int, default=100, help="Number of largest files to record.")
    parser.add_argument("--time-limit", type=int, default=600, help="Maximum scan duration in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Scan root does not exist: {root}")
    if args.top_files < 1:
        raise SystemExit("--top-files must be at least 1")
    if args.time_limit < 1:
        raise SystemExit("--time-limit must be at least 1 second")

    report = scan(root, Path(args.output).resolve(), args.top_files, args.time_limit)
    disk = report["disk"]
    print(f"Scanned: {report['scan_root']}")
    print(f"Files checked: {report['files_seen']:,}")
    print(f"Used: {format_bytes(disk['used_bytes'])} / {format_bytes(disk['total_bytes'])}")
    print(f"Free: {format_bytes(disk['free_bytes'])}")
    print(f"Report: {Path(args.output).resolve()}")
    if report["timed_out"]:
        print("Warning: the time limit was reached, so the report is partial.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
