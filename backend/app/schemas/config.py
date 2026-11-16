from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.common import APIModel


class CpuInfoOut(APIModel):
    name: str
    logical_cores: int | None = None


class MemoryInfoOut(APIModel):
    total_mb: int | None = None
    available_mb: int | None = None


class GpuDeviceOut(APIModel):
    vendor: str
    backend: str
    name: str
    memory_total_mb: int | None = None
    memory_used_mb: int | None = None
    driver: str | None = None
    compute_capability: str | None = None


class RuntimeConfigOut(APIModel):
    device: str = "cpu"
    device_preference: str = "auto"
    available_devices: list[str] = Field(default_factory=lambda: ["cpu"])
    gpu_devices: list[GpuDeviceOut] = Field(default_factory=list)
    cpu: CpuInfoOut = Field(default_factory=CpuInfoOut)
    memory: MemoryInfoOut = Field(default_factory=MemoryInfoOut)
    llm_configured: bool = False
    llm_provider: str = "openai-compatible"
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    jev_configured: bool = False
    jev_provider: str = "typesafe"
    jev_model: str = ""
    targets: list[str] = Field(default_factory=lambda: ["laya"])
    reserved_targets: list[str] = Field(default_factory=lambda: ["gliner"])
    laya_enabled: bool = True
    gliner_enabled: bool = False
    laya_runtime_ready: bool = False
    laya_train_ready: bool = False
    laya_serve_ready: bool = False
    laya_venv: str = ""
    laya_models: dict[str, str] = Field(default_factory=dict)
    gliner_runtime_ready: bool = False
    gliner_venv: str = ""
    gliner_models: dict[str, str] = Field(default_factory=dict)
    data_dir: str = ""
    models_dir: str = ""
    artifact_dir: str = ""


class DeviceUpdate(APIModel):
    device: Literal["auto", "cpu", "cuda", "mps", "rocm"] = "auto"
