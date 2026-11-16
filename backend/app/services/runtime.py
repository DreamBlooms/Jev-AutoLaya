from __future__ import annotations

import json
import platform
import shutil
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.errors import ApiError

DEVICE_PRIORITY = ("cuda", "rocm", "mps", "cpu")
ALLOWED_DEVICES = {"auto", *DEVICE_PRIORITY}


def available_devices() -> list[str]:
    devices = ["cpu"]
    if shutil.which("nvidia-smi"):
        devices.insert(0, "cuda")
    if shutil.which("rocm-smi"):
        devices.insert(0, "rocm")
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        devices.insert(0, "mps")
    return devices


def resolve_device(preference: str) -> str:
    available = available_devices()
    if preference == "auto":
        for device in DEVICE_PRIORITY:
            if device in available:
                return device
        return "cpu"
    if preference not in ALLOWED_DEVICES:
        raise ApiError(422, "VALIDATION_ERROR", f"Unsupported device: {preference}")
    if preference not in available:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"Device '{preference}' is not available on this machine",
        )
    return preference


def _runtime_path() -> Path:
    settings = get_settings()
    settings.ensure_dirs()
    return settings.data_dir / "runtime.json"


def _read_runtime() -> dict[str, Any]:
    path = _runtime_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def get_device_preference() -> str:
    preference = _read_runtime().get("device", "auto")
    return preference if preference in ALLOWED_DEVICES else "auto"


def set_device_preference(device: str) -> str:
    if device not in ALLOWED_DEVICES:
        raise ApiError(422, "VALIDATION_ERROR", f"Unsupported device: {device}")
    resolve_device(device)
    path = _runtime_path()
    current = _read_runtime()
    current["device"] = device
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return device


def runtime_summary() -> dict[str, Any]:
    settings = get_settings()
    preference = get_device_preference()
    return {
        "device": resolve_device(preference),
        "device_preference": preference,
        "available_devices": available_devices(),
        "llm_configured": bool(settings.llm_api_key),
        "llm_provider": settings.llm_provider,
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "jev_configured": bool(settings.typesafe_api_key or settings.openrouter_api_key),
        "jev_provider": settings.jev_provider,
        "jev_model": settings.resolved_jev_model,
        "targets": (
            (["laya"] if settings.laya_enabled else [])
            + (["gliner"] if settings.gliner_enabled else [])
        ),
        "reserved_targets": [] if settings.gliner_enabled else ["gliner"],
        "laya_enabled": settings.laya_enabled,
        "gliner_enabled": settings.gliner_enabled,
        "gliner_runtime_ready": settings.gliner_runtime_ready,
        "gliner_venv": str(settings.resolved_gliner_venv),
        "gliner_models": {
            "english": settings.gliner_base_model,
            "multilingual": settings.gliner_multi_model,
        },
        "laya_runtime_ready": settings.laya_runtime_ready,
        "laya_train_ready": bool(settings.resolved_laya_train_bin),
        "laya_serve_ready": bool(settings.resolved_laya_serve_bin),
        "laya_venv": str(settings.resolved_laya_venv),
        "laya_models": {
            "default": settings.laya_base_model,
            "multilingual": settings.laya_multi_model,
        },
        "data_dir": str(settings.data_dir),
    }
