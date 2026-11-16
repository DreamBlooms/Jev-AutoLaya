from __future__ import annotations

from app.services import runtime


def test_cuda_detection_and_auto_resolution(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime.shutil,
        "which",
        lambda name: "/usr/bin/nvidia-smi" if name == "nvidia-smi" else None,
    )
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    monkeypatch.setattr(runtime.platform, "machine", lambda: "x86_64")
    assert "cuda" in runtime.available_devices()
    assert runtime.resolve_device("auto") == "cuda"
    assert runtime.resolve_device("cuda") == "cuda"
