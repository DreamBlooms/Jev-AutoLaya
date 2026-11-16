from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any


def cpu_info() -> dict[str, Any]:
    name = ""
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        try:
            for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("model name"):
                    name = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
    if not name:
        name = platform.processor() or platform.machine() or "Unknown CPU"
    return {
        "name": name,
        "logical_cores": os.cpu_count(),
    }


def memory_info() -> dict[str, Any]:
    total_mb: int | None = None
    available_mb: int | None = None
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        try:
            values: dict[str, int] = {}
            for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
                key, _, raw = line.partition(":")
                if not raw:
                    continue
                parts = raw.strip().split()
                if not parts:
                    continue
                values[key] = int(parts[0])
            if "MemTotal" in values:
                total_mb = values["MemTotal"] // 1024
            if "MemAvailable" in values:
                available_mb = values["MemAvailable"] // 1024
        except (OSError, ValueError):
            pass
    if total_mb is None:
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_mb = int(page_size * os.sysconf("SC_PHYS_PAGES") / (1024 * 1024))
            available_mb = int(page_size * os.sysconf("SC_AVPHYS_PAGES") / (1024 * 1024))
        except (ValueError, OSError, AttributeError):
            pass
    return {
        "total_mb": total_mb,
        "available_mb": available_mb,
    }
