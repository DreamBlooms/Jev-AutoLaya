from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models import TrainingJob

EPOCH_LOSS_RE = re.compile(
    r"epoch\s+(\d+)\s*/\s*(\d+)\s+mean\s+loss\s+([0-9.eE+-]+)",
    re.IGNORECASE,
)
STEP_LOSS_RE = re.compile(r"step\s+(\d+)\s+loss\s+([0-9.eE+-]+)", re.IGNORECASE)
LOSS_RE = re.compile(r"loss=([0-9.eE+-]+)")
LR_RE = re.compile(r"lr=([0-9.eE+-]+)")


def _series(key: str, points: list[dict[str, Any]]) -> dict[str, Any] | None:
    values = [point for point in points if point.get("value") is not None]
    return {"key": key, "points": values} if values else None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_log(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _gliner(job: TrainingJob, report: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    series: list[dict[str, Any]] = []
    train_history = report.get("train_metrics_history") or []
    eval_history = report.get("eval_metrics_history") or []
    loss_points = [
        {"step": item.get("step"), "epoch": item.get("epoch"), "value": item.get("loss")}
        for item in train_history
        if isinstance(item, dict)
    ]
    for key, field in (
        ("loss", "loss"),
        ("classification_loss", "classification_loss"),
        ("structure_loss", "structure_loss"),
        ("count_loss", "count_loss"),
        ("learning_rate", "learning_rate"),
        ("throughput", "throughput"),
    ):
        points = [
            {
                "step": item.get("step"),
                "epoch": item.get("epoch"),
                "value": item.get(field),
            }
            for item in train_history
            if isinstance(item, dict)
        ]
        if key == "loss":
            points = loss_points
        value = _series(key, points)
        if value:
            series.append(value)
    for key, field in (
        ("eval_loss", "eval_loss"),
        ("eval_classification_loss", "eval_classification_loss"),
        ("eval_structure_loss", "eval_structure_loss"),
        ("eval_count_loss", "eval_count_loss"),
    ):
        points = [
            {
                "step": item.get("step"),
                "epoch": item.get("epoch"),
                "value": item.get(field),
            }
            for item in eval_history
            if isinstance(item, dict)
        ]
        value = _series(key, points)
        if value:
            series.append(value)
    if not series:
        warnings.append("No metric history was found in the GLiNER training report.")
    return {
        "series": series,
        "summary": {
            "total_steps": report.get("total_steps"),
            "total_epochs": report.get("total_epochs"),
            "total_time_seconds": report.get("total_time_seconds"),
            "samples_per_second": report.get("samples_per_second"),
            "best_metric": report.get("best_metric"),
        },
        "heads": [],
    }


def _laya_finetune(job: TrainingJob, report: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    root = Path(job.log_path).parent if job.log_path else None
    metrics = _read_json(root / "checkpoint" / "laya_metrics.json") if root else {}
    lines = _read_log(Path(job.log_path) if job.log_path else None)
    series: list[dict[str, Any]] = []
    loss_points: list[dict[str, Any]] = []
    step_loss_points: list[dict[str, Any]] = []
    lr_encoder_points: list[dict[str, Any]] = []
    lr_head_points: list[dict[str, Any]] = []
    lr_single_points: list[dict[str, Any]] = []
    step = 0
    for line in lines:
        match = EPOCH_LOSS_RE.search(line)
        if match:
            epoch = int(match.group(1))
            step += 1
            loss_points.append({"step": step, "epoch": epoch, "value": float(match.group(3))})
            continue
        step_match = STEP_LOSS_RE.search(line)
        if step_match:
            step_loss_points.append(
                {
                    "step": int(step_match.group(1)),
                    "epoch": None,
                    "value": float(step_match.group(2)),
                }
            )
            continue
        loss_match = LOSS_RE.search(line)
        lr_match = LR_RE.search(line)
        if loss_match or lr_match:
            step += 1
            if loss_match:
                step_loss_points.append(
                    {"step": step, "epoch": None, "value": float(loss_match.group(1))}
                )
            if lr_match:
                lr_single_points.append(
                    {"step": step, "epoch": None, "value": float(lr_match.group(1))}
                )
    epoch_loss = metrics.get("epoch_loss") if isinstance(metrics.get("epoch_loss"), list) else []
    if epoch_loss:
        loss_points = [
            {"step": index + 1, "epoch": index + 1, "value": float(value)}
            for index, value in enumerate(epoch_loss)
            if isinstance(value, (int, float))
        ]
    lr_history = (
        metrics.get("learning_rate") if isinstance(metrics.get("learning_rate"), list) else []
    )
    for item in lr_history:
        if not isinstance(item, dict):
            continue
        values = item.get("values")
        if not isinstance(values, list) or not values:
            continue
        step_number = item.get("step")
        if len(values) >= 2:
            lr_encoder_points.append(
                {"step": step_number, "epoch": None, "value": float(values[0])}
            )
            lr_head_points.append({"step": step_number, "epoch": None, "value": float(values[1])})
        else:
            lr_single_points.append({"step": step_number, "epoch": None, "value": float(values[0])})
    for key, points in (
        ("loss", loss_points),
        ("loss_step", step_loss_points),
        ("learning_rate_encoder", lr_encoder_points),
        ("learning_rate_head", lr_head_points),
        ("learning_rate", lr_single_points),
    ):
        value = _series(key, points)
        if value:
            series.append(value)
    if not loss_points and not step_loss_points:
        warnings.append("No loss history was found for this Laya training run.")
    if not lr_encoder_points and not lr_head_points and not lr_single_points:
        warnings.append("No learning-rate history was found for this Laya training run.")
    before = report.get("before") if isinstance(report.get("before"), dict) else {}
    after = report.get("after") if isinstance(report.get("after"), dict) else {}
    return {
        "series": series,
        "summary": {
            "before": before,
            "after": after,
            "eval_mode": report.get("eval_mode"),
            "is_held_out": report.get("is_held_out"),
            "eval_items": report.get("eval_items"),
        },
        "heads": [],
    }


def _laya_fit(report: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    raw_heads = report.get("heads") if isinstance(report.get("heads"), dict) else {}
    heads = []
    for key, value in raw_heads.items():
        if not isinstance(value, dict):
            continue
        calibration = (
            (report.get("calibration") or {}).get("questions", {}).get(key, {})
            if isinstance(report.get("calibration"), dict)
            else {}
        )
        heads.append(
            {
                "key": key,
                "fitted": value.get("fitted"),
                "examples": value.get("examples"),
                "cv_accuracy": value.get("cv_accuracy"),
                "engine_accuracy": value.get("engine_accuracy"),
                "ece_before": calibration.get("ece_before"),
                "ece_after": calibration.get("ece_after"),
                "temperature": calibration.get("temperature"),
                "chance": value.get("chance"),
                "used_by_auto": value.get("used_by_auto"),
                "reason": value.get("reason"),
            }
        )
    if not heads:
        warnings.append("No head metrics were found in the Fit report.")
    if report.get("warning"):
        warnings.append(str(report["warning"]))
    warnings.append("Fit produces head calibration metrics rather than Loss/LR curves.")
    return {
        "series": [],
        "summary": {
            "n_rows": report.get("n_rows"),
            "n_fit": report.get("n_fit"),
            "n_calibrate": report.get("n_calibrate"),
            "serving": report.get("serving"),
            "kept": report.get("kept"),
        },
        "heads": heads,
    }


def build_training_charts(job: TrainingJob) -> dict[str, Any]:
    warnings: list[str] = []
    root = Path(job.log_path).parent if job.log_path else None
    if job.target == "gliner":
        report_path = root / "gliner" / "gliner_train_report.json" if root else None
        report = _read_json(report_path) if report_path else {}
        payload = _gliner(job, report, warnings)
    elif job.mode == "fit":
        report_path = root / "calibration" / "fit_report.json" if root else None
        report = _read_json(report_path) if report_path else {}
        payload = _laya_fit(report, warnings)
    else:
        report_path = root / "checkpoint" / "train_report.json" if root else None
        report = _read_json(report_path) if report_path else {}
        payload = _laya_finetune(job, report, warnings)
    return {
        "target": job.target,
        "mode": job.mode,
        "series": payload["series"],
        "summary": payload["summary"],
        "heads": payload["heads"],
        "warnings": warnings,
        "log_path": job.log_path,
    }
