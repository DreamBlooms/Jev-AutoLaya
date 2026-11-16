from __future__ import annotations

from math import isfinite
from typing import Any

from app.core.errors import ApiError
from app.models import Question


def _confidence(value: Any, default: float = 1.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(422, "VALIDATION_ERROR", "Confidence must be a number") from exc
    if not isfinite(result) or result < 0 or result > 1:
        raise ApiError(422, "VALIDATION_ERROR", "Confidence must be between 0 and 1")
    return result


def _probabilities(raw: Any, expected_keys: list[str]) -> dict[str, float] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ApiError(422, "VALIDATION_ERROR", "Probabilities must be an object")
    values: dict[str, float] = {}
    for key in expected_keys:
        try:
            value = float(raw.get(key, 0))
        except (TypeError, ValueError) as exc:
            raise ApiError(422, "VALIDATION_ERROR", f"Invalid probability for {key}") from exc
        if not isfinite(value) or value < 0:
            raise ApiError(422, "VALIDATION_ERROR", f"Invalid probability for {key}")
        values[key] = value
    total = sum(values.values())
    if total <= 0:
        raise ApiError(422, "VALIDATION_ERROR", "Probabilities must have a positive sum")
    return {key: round(value / total, 6) for key, value in values.items()}


def _choice(question: Question, raw: Any) -> dict[str, Any]:
    criteria = question.criteria if isinstance(question.criteria, dict) else {}
    if not criteria:
        raise ApiError(422, "VALIDATION_ERROR", "Choice question has no options")
    value = raw
    confidence: Any = None
    probabilities: Any = None
    if isinstance(raw, dict):
        value = raw.get("choice", raw.get("value", raw.get("label")))
        confidence = raw.get("confidence")
        probabilities = raw.get("probabilities")
    if not isinstance(value, str) or value not in criteria:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            f"Choice answer must be one of: {', '.join(criteria)}",
        )
    normalized_probabilities = _probabilities(probabilities, list(criteria))
    if normalized_probabilities is not None:
        resolved_confidence = normalized_probabilities[value]
        if confidence is not None:
            resolved_confidence = _confidence(confidence)
    else:
        resolved_confidence = _confidence(confidence)
        remaining = max(0.0, 1.0 - resolved_confidence)
        others = [key for key in criteria if key != value]
        normalized_probabilities = {
            key: round(remaining / len(others), 6) if others else 0.0 for key in criteria
        }
        normalized_probabilities[value] = round(resolved_confidence, 6)
    return {
        "choice": value,
        "confidence": round(resolved_confidence, 6),
        "probabilities": normalized_probabilities,
    }


def _noul(question: Question, raw: Any) -> dict[str, Any]:
    value = raw
    confidence: Any = None
    probabilities: Any = None
    if isinstance(raw, dict):
        value = raw.get("noul", raw.get("value", raw.get("label", raw.get("answer"))))
        confidence = raw.get("confidence")
        probabilities = raw.get("probabilities")
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"yes", "true", "1", "是", "对"}:
            value = 1.0
        elif lowered in {"no", "false", "0", "否", "不"}:
            value = 0.0
        else:
            try:
                value = float(lowered)
            except ValueError as exc:
                raise ApiError(
                    422,
                    "VALIDATION_ERROR",
                    "Noul answer must be yes/no or a probability between 0 and 1",
                ) from exc
    if isinstance(value, bool):
        value = 1.0 if value else 0.0
    try:
        probability = float(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Noul answer must be yes/no or a probability between 0 and 1",
        ) from exc
    if not isfinite(probability) or probability < 0 or probability > 1:
        raise ApiError(422, "VALIDATION_ERROR", "Noul probability must be between 0 and 1")
    if isinstance(probabilities, dict) and "yes" not in probabilities and "true" in probabilities:
        probabilities = {
            "yes": probabilities.get("true", probability),
            "no": probabilities.get("false", 1.0 - probability),
        }
    normalized_probabilities = _probabilities(probabilities, ["yes", "no"])
    if normalized_probabilities is None:
        normalized_probabilities = {
            "yes": round(probability, 6),
            "no": round(1.0 - probability, 6),
        }
    resolved_confidence = (
        _confidence(confidence) if confidence is not None else max(probability, 1.0 - probability)
    )
    return {
        "noul": round(probability, 6),
        "confidence": round(resolved_confidence, 6),
        "probabilities": normalized_probabilities,
    }


def _score(question: Question, raw: Any) -> dict[str, Any]:
    labels = question.criteria if isinstance(question.criteria, list) else None
    value = raw
    confidence: Any = None
    probabilities: Any = None
    if isinstance(raw, dict):
        value = raw.get("score", raw.get("value", raw.get("label", raw.get("answer"))))
        confidence = raw.get("confidence")
        probabilities = raw.get("probabilities")
    if labels and isinstance(value, str) and value in labels:
        value = labels.index(value)
    if isinstance(value, bool):
        raise ApiError(422, "VALIDATION_ERROR", "Score answer must be a number")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(422, "VALIDATION_ERROR", "Score answer must be a number") from exc
    if not isfinite(score):
        raise ApiError(422, "VALIDATION_ERROR", "Score answer must be finite")
    if labels:
        if score < 0 or score > len(labels) - 1:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                f"Score must be between 0 and {len(labels) - 1}",
            )
    elif score < 0 or score > 100:
        raise ApiError(422, "VALIDATION_ERROR", "Score must be between 0 and 100")
    score = int(round(score))
    normalized_probabilities = None
    if probabilities is not None and labels:
        if not isinstance(probabilities, dict):
            raise ApiError(422, "VALIDATION_ERROR", "Probabilities must be an object")
        values: dict[str, float] = {}
        for index, label in enumerate(labels):
            raw = probabilities.get(label, probabilities.get(str(index), 0))
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ApiError(422, "VALIDATION_ERROR", f"Invalid probability for {label}") from exc
            if not isfinite(value) or value < 0:
                raise ApiError(422, "VALIDATION_ERROR", f"Invalid probability for {label}")
            values[label] = value
        total = sum(values.values())
        if total <= 0:
            raise ApiError(422, "VALIDATION_ERROR", "Probabilities must have a positive sum")
        normalized_probabilities = {
            label: round(value / total, 6) for label, value in values.items()
        }
    elif probabilities is not None:
        expected = [str(index) for index in range(int(score) + 1)]
        normalized_probabilities = _probabilities(probabilities, expected)
    return {
        "score": int(score),
        "confidence": round(_confidence(confidence), 6),
        "probabilities": normalized_probabilities,
    }


def normalize_answer(question: Question, raw: Any) -> dict[str, Any]:
    if raw is None:
        raise ApiError(422, "VALIDATION_ERROR", "Answer is required")
    if question.type == "choice":
        return _choice(question, raw)
    if question.type == "noul":
        return _noul(question, raw)
    if question.type == "score":
        return _score(question, raw)
    raise ApiError(422, "VALIDATION_ERROR", f"Unsupported question type: {question.type}")
