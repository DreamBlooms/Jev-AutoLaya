from __future__ import annotations

import shutil
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AutoLaya"
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    data_dir: Path = ROOT_DIR / "data"
    database_url: str = ""

    llm_provider: str = "openai-compatible"
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    llm_api_key: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 120
    llm_max_concurrency: int = 4

    jev_provider: str = "typesafe"
    typesafe_api_key: str = ""
    openrouter_api_key: str = ""
    jev_model: str = ""
    typesafe_jev_model: str = "jev-1.14.0"
    openrouter_jev_model: str = "~typesafe/jev-latest"
    typesafe_base_url: str = ""
    openrouter_base_url: str = "https://openrouter.ai"
    jev_timeout_seconds: int = 90

    laya_enabled: bool = True
    laya_base_model: str = "convaiinnovations/laya-typed-decisions"
    laya_multi_model: str = "convaiinnovations/laya-multilingual"
    laya_fit_model: str = ""
    laya_fit_backbone: str = ""
    laya_device: str = "auto"
    laya_serve_host: str = "127.0.0.1"
    laya_serve_port: int = 8100
    laya_api_key: str = ""
    laya_venv_dir: Path = BACKEND_DIR / "laya-venv"
    laya_train_bin: str = ""
    laya_serve_bin: str = ""

    generation_batch_size: int = 20
    generation_max_attempts: int = 3
    teacher_max_concurrency: int = 4
    eval_max_rows: int = 200
    job_worker_enabled: bool = True

    hf_endpoint: str = ""

    gliner_enabled: bool = False
    gliner_base_model: str = "fastino/GLiNER2.5-Decide"
    gliner_multi_model: str = "fastino/GLiNER2.5-multi-Decide"
    gliner_device: str = "auto"
    gliner_serve_host: str = "127.0.0.1"
    gliner_serve_port: int = 8101
    gliner_venv_dir: Path = BACKEND_DIR / "gliner-venv"

    dataset_dir: Path | None = None
    artifact_dir: Path | None = None
    upload_dir: Path | None = None

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'autolaya.db').as_posix()}"

    @property
    def resolved_dataset_dir(self) -> Path:
        return self.dataset_dir or self.data_dir / "datasets"

    @property
    def resolved_artifact_dir(self) -> Path:
        return self.artifact_dir or self.data_dir / "artifacts"

    @property
    def resolved_upload_dir(self) -> Path:
        return self.upload_dir or self.data_dir / "uploads"

    @property
    def jev_configured(self) -> bool:
        return bool(self.resolved_jev_api_key)

    @property
    def resolved_jev_provider(self) -> str:
        return (self.jev_provider or "typesafe").strip().lower()

    @property
    def resolved_jev_api_key(self) -> str:
        if self.resolved_jev_provider == "openrouter":
            return self.openrouter_api_key.strip()
        return self.typesafe_api_key.strip()

    @property
    def resolved_jev_model(self) -> str:
        if self.jev_model.strip():
            return self.jev_model.strip()
        if self.resolved_jev_provider == "openrouter":
            return self.openrouter_jev_model.strip()
        return self.typesafe_jev_model.strip()

    @property
    def resolved_jev_base_url(self) -> str:
        if self.resolved_jev_provider == "openrouter":
            return (self.openrouter_base_url or "https://openrouter.ai").rstrip("/")
        return self.typesafe_base_url.strip()

    @property
    def resolved_laya_venv(self) -> Path:
        return self.laya_venv_dir

    @property
    def resolved_laya_python(self) -> str:
        candidate = self.resolved_laya_venv / "bin" / "python"
        if candidate.exists():
            return str(candidate)
        return sys.executable

    @property
    def resolved_laya_train_bin(self) -> str:
        if self.laya_train_bin.strip():
            return self.laya_train_bin.strip()
        candidate = self.resolved_laya_venv / "bin" / "laya-train"
        if candidate.exists():
            return str(candidate)
        return shutil.which("laya-train") or ""

    @property
    def resolved_laya_serve_bin(self) -> str:
        if self.laya_serve_bin.strip():
            return self.laya_serve_bin.strip()
        candidate = self.resolved_laya_venv / "bin" / "laya-serve"
        if candidate.exists():
            return str(candidate)
        return shutil.which("laya-serve") or ""

    @property
    def resolved_gliner_venv(self) -> Path:
        return self.gliner_venv_dir

    @property
    def resolved_gliner_python(self) -> str:
        candidate = self.resolved_gliner_venv / "bin" / "python"
        if candidate.exists():
            return str(candidate)
        return sys.executable

    @property
    def gliner_runtime_ready(self) -> bool:
        return (self.resolved_gliner_venv / "bin" / "python").exists()

    @property
    def laya_runtime_ready(self) -> bool:
        probe = self.resolved_laya_venv / "bin" / "python"
        return probe.exists() and bool(self.resolved_laya_train_bin or self.resolved_laya_serve_bin)

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.resolved_dataset_dir,
            self.resolved_artifact_dir,
            self.resolved_upload_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
