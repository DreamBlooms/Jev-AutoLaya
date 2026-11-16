from __future__ import annotations

import csv
import json
import subprocess
from typing import Any

MIB = 1024 * 1024


def _run(command: list[str]) -> str:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    return process.stdout.strip() if process.returncode == 0 else ""


def _nvidia_devices() -> list[dict[str, Any]]:
    output = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,driver_version,compute_cap",
            "--format=csv,noheader,nounits",
        ]
    )
    devices: list[dict[str, Any]] = []
    for row in csv.reader(output.splitlines()):
        if not row or not row[0].strip():
            continue
        values = [value.strip() for value in row]
        name = values[0]
        total = int(float(values[1])) if len(values) > 1 and values[1] not in {"", "N/A"} else None
        used = int(float(values[2])) if len(values) > 2 and values[2] not in {"", "N/A"} else None
        devices.append(
            {
                "vendor": "NVIDIA",
                "backend": "cuda",
                "name": name,
                "memory_total_mb": total,
                "memory_used_mb": used,
                "driver": values[3] if len(values) > 3 and values[3] not in {"", "N/A"} else None,
                "compute_capability": (
                    values[4] if len(values) > 4 and values[4] not in {"", "N/A"} else None
                ),
            }
        )
    return devices


def _rocm_devices() -> list[dict[str, Any]]:
    output = _run(
        [
            "rocm-smi",
            "--showproductname",
            "--showmeminfo",
            "vram",
            "--showdriverversion",
            "--json",
        ]
    )
    if not output:
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    system = payload.get("system") or {}
    driver = system.get("Driver version")
    devices: list[dict[str, Any]] = []
    for key, card in payload.items():
        if not key.startswith("card") or not isinstance(card, dict):
            continue
        name = card.get("Card Series") or card.get("Card Model") or card.get("Card SKU") or key
        total_bytes = card.get("VRAM Total Memory (B)")
        used_bytes = card.get("VRAM Total Used Memory (B)")
        devices.append(
            {
                "vendor": card.get("Card Vendor") or "AMD",
                "backend": "rocm",
                "name": str(name),
                "memory_total_mb": int(total_bytes) // MIB if total_bytes else None,
                "memory_used_mb": int(used_bytes) // MIB if used_bytes else None,
                "driver": card.get("Driver version") or driver,
                "compute_capability": card.get("GFX Version"),
            }
        )
    return devices


def detect_gpu_devices() -> list[dict[str, Any]]:
    devices = _nvidia_devices()
    if devices:
        return devices
    return _rocm_devices()
