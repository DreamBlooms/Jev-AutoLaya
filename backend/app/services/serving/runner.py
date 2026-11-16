from __future__ import annotations

import contextlib
import logging
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import ApiError
from app.models import Deployment, ModelArtifact
from app.schemas.jobs import DeploymentCreate
from app.services.runtime import get_device_preference

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _find_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        if _port_available(host, port):
            return port
    raise ApiError(409, "DEPLOYMENT_ERROR", "No free port found for Laya server")


def _health(host: str, port: int) -> bool:
    target = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with urllib.request.urlopen(f"http://{target}:{port}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _source(artifact: ModelArtifact) -> tuple[str, str, str, str]:
    settings = get_settings()
    if artifact.target == "gliner":
        return artifact.path, "", "gliner", ""
    if artifact.kind == "checkpoint":
        return artifact.path, "", "checkpoint", ""
    if artifact.kind == "calibration":
        return (
            str(
                artifact.config.get("base_model")
                or settings.laya_fit_model
                or "nandakishorm/vega-U"
            ),
            artifact.path,
            "fit",
            str(artifact.config.get("backbone") or settings.laya_fit_backbone),
        )
    raise ApiError(422, "DEPLOYMENT_ERROR", f"Unsupported artifact kind: {artifact.kind}")


def create_deployment(db: Session, payload: DeploymentCreate) -> Deployment:
    settings = get_settings()
    if not settings.laya_runtime_ready:
        raise ApiError(
            400,
            "DEPLOYMENT_ERROR",
            "Laya runtime is not installed. Run ./deploy.sh setup-laya first.",
        )
    artifact = db.get(ModelArtifact, payload.artifact_id)
    if artifact is None:
        raise ApiError(404, "NOT_FOUND", "Model artifact not found")
    if payload.target == "gliner":
        host = payload.host or settings.gliner_serve_host
        port = payload.port or _find_port(host, settings.gliner_serve_port)
    else:
        host = payload.host or settings.laya_serve_host
        port = payload.port or _find_port(host, settings.laya_serve_port)
    if not _port_available(host, port):
        raise ApiError(409, "DEPLOYMENT_ERROR", f"Port {port} is already in use")
    deployment = Deployment(
        artifact_id=artifact.id,
        target=payload.target,
        host=host,
        port=port,
        status="starting",
        started_at=_now(),
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    _spawn(deployment, artifact)
    return deployment


def _spawn(deployment: Deployment, artifact: ModelArtifact) -> None:
    settings = get_settings()
    source, calibration, mode, backbone = _source(artifact)
    directory = settings.resolved_artifact_dir / "deployments" / deployment.id
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "serve.log"
    deployment.log_path = str(log_path)
    if mode == "gliner":
        script = Path(__file__).with_name("gliner_server.py")
        command = [
            settings.resolved_gliner_python,
            str(script),
            "--model",
            source,
            "--host",
            deployment.host,
            "--port",
            str(deployment.port),
            "--device",
            (
                get_device_preference()
                if settings.gliner_device == "auto"
                else settings.gliner_device
            ),
        ]
    else:
        script = Path(__file__).with_name("laya_server.py")
        command = [
            settings.resolved_laya_python,
            str(script),
            "--model",
            source,
            "--host",
            deployment.host,
            "--port",
            str(deployment.port),
            "--device",
            "cuda" if get_device_preference() == "rocm" else get_device_preference(),
            "--mode",
            mode,
        ]
    if calibration:
        command.extend(["--calibration", calibration])
    if backbone:
        command.extend(["--backbone", backbone])
    if settings.laya_api_key and mode != "gliner":
        command.extend(["--api-key", settings.laya_api_key])
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if settings.gliner_device == "cpu" and mode == "gliner":
        env["CUDA_VISIBLE_DEVICES"] = ""
    if settings.hf_endpoint:
        env["HF_ENDPOINT"] = settings.hf_endpoint
    log = log_path.open("w", encoding="utf-8")
    log.write("$ " + " ".join(command) + "\n")
    log.flush()
    process = subprocess.Popen(
        command,
        cwd=directory,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        start_new_session=True,
    )
    db = SessionLocal()
    try:
        record = db.get(Deployment, deployment.id)
        if record is not None:
            record.pid = process.pid
            record.log_path = str(log_path)
            record.status = "starting"
            db.commit()
    finally:
        db.close()
    threading.Thread(
        target=_monitor,
        args=(deployment.id, process.pid, deployment.host, deployment.port),
        daemon=True,
    ).start()


def _monitor(deployment_id: str, pid: int, host: str, port: int) -> None:
    while True:
        time.sleep(1.5)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            db = SessionLocal()
            try:
                record = db.get(Deployment, deployment_id)
                if record is not None and record.status != "stopped":
                    record.status = "failed"
                    record.error = "Laya server process exited"
                    db.commit()
            finally:
                db.close()
            return
        if _health(host, port):
            db = SessionLocal()
            try:
                record = db.get(Deployment, deployment_id)
                if record is not None and record.status == "starting":
                    record.status = "running"
                    record.error = None
                    db.commit()
            finally:
                db.close()


def stop_deployment(db: Session, deployment: Deployment) -> Deployment:
    if deployment.pid:
        try:
            os.killpg(os.getpgid(deployment.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(deployment.pid, signal.SIGTERM)
    deployment.status = "stopped"
    deployment.stopped_at = _now()
    deployment.pid = None
    db.commit()
    db.refresh(deployment)
    return deployment


def restart_deployment(db: Session, deployment: Deployment) -> Deployment:
    artifact = db.get(ModelArtifact, deployment.artifact_id) if deployment.artifact_id else None
    if artifact is None:
        raise ApiError(404, "NOT_FOUND", "Model artifact not found")
    stop_deployment(db, deployment)
    deployment.status = "starting"
    deployment.started_at = _now()
    deployment.stopped_at = None
    deployment.error = None
    db.commit()
    _spawn(deployment, artifact)
    db.refresh(deployment)
    return deployment
