from __future__ import annotations

import re
from typing import Any

from app.core.errors import ApiError

KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
QUESTION_TYPES = {"choice", "noul", "score"}


def validate_key(key: str) -> str:
    value = key.strip()
    if not KEY_RE.fullmatch(value):
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Question key must start with a letter and contain only "
            "letters, digits, or underscores",
        )
    return value


def validate_question_fields(
    question_type: str,
    criteria: Any,
) -> dict[str, str] | list[str] | None:
    if question_type not in QUESTION_TYPES:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Question type must be one of: choice, noul, score",
        )

    if question_type == "choice":
        if not isinstance(criteria, dict) or not criteria:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Choice questions require a non-empty criteria object",
            )
        normalized: dict[str, str] = {}
        for raw_key, raw_description in criteria.items():
            key = str(raw_key).strip()
            if not key:
                raise ApiError(422, "VALIDATION_ERROR", "Choice option keys cannot be empty")
            if key in normalized:
                raise ApiError(422, "VALIDATION_ERROR", f"Duplicate choice option: {key}")
            normalized[key] = str(raw_description).strip()
        return normalized

    if question_type == "score":
        if criteria is None or criteria == []:
            return None
        if not isinstance(criteria, list) or not all(
            isinstance(item, (str, int, float)) and str(item).strip() for item in criteria
        ):
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "Score criteria must be a list of non-empty labels",
            )
        labels = [str(item).strip() for item in criteria]
        if len(set(labels)) != len(labels):
            raise ApiError(422, "VALIDATION_ERROR", "Score labels must be unique")
        return labels

    if criteria not in (None, {}, []):
        raise ApiError(422, "VALIDATION_ERROR", "Noul questions do not accept criteria")
    return None
