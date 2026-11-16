from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings
from app.core.errors import ApiError
from app.models import Question
from app.services.answers import normalize_answer


class JevTeacherError(RuntimeError):
    pass


def _question_payload(question: Question) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": question.type,
        "instructions": question.instructions or question.key,
    }
    if question.type == "choice":
        payload["criteria"] = question.criteria or {}
    elif question.type == "score" and question.criteria:
        payload["criteria"] = question.criteria
    return payload


def _to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


class JevTeacher:
    def __init__(self, transport: Any | None = None) -> None:
        self.settings = get_settings()
        self.transport = transport
        if transport is None and not self.settings.jev_configured:
            raise JevTeacherError(
                "Jev is not configured. Set TYPESAFE_API_KEY or OPENROUTER_API_KEY."
            )

    def label(self, state: dict[str, Any], questions: list[Question]) -> dict[str, dict[str, Any]]:
        if not questions:
            raise JevTeacherError("No questions to label")
        payload = {question.key: _question_payload(question) for question in questions}
        response = self._ask(state, payload)
        answers = _to_dict(response.get("answers")) if isinstance(response, dict) else {}
        if not answers and hasattr(response, "answers"):
            answers = _to_dict(response.answers)
        if not answers:
            raise JevTeacherError("Jev response did not include answers")
        model = str(response.get("model") or self.settings.resolved_jev_model)
        output: dict[str, dict[str, Any]] = {}
        for question in questions:
            raw = answers.get(question.key)
            if raw is None:
                raise JevTeacherError(f"Jev did not answer question '{question.key}'")
            try:
                answer = normalize_answer(question, _to_dict(raw))
            except ApiError as exc:
                raise JevTeacherError(exc.message) from exc
            output[question.key] = {
                "answer": answer,
                "teacher": "jev",
                "teacher_model": model,
                "confidence": answer.get("confidence"),
                "probabilities": answer.get("probabilities"),
            }
        return output

    def _ask(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        if self.transport is not None:
            return _to_dict(
                self.transport.ask(
                    model=self.settings.resolved_jev_model,
                    state=state,
                    questions=questions,
                )
            )
        if self.settings.resolved_jev_provider == "openrouter":
            return self._ask_openrouter(state, questions)
        return self._ask_typesafe(state, questions)

    def _ask_typesafe(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        try:
            from typesafe_sdk import TypeSafeClient
        except ImportError as exc:
            raise JevTeacherError(
                "typesafe-sdk is not installed. Run: pip install typesafe-sdk"
            ) from exc
        kwargs: dict[str, Any] = {
            "api_key": self.settings.resolved_jev_api_key,
            "timeout": self.settings.jev_timeout_seconds,
        }
        if self.settings.resolved_jev_base_url:
            kwargs["base_url"] = self.settings.resolved_jev_base_url
        try:
            with TypeSafeClient(**kwargs) as client:
                response = client.system_one(
                    state=state,
                    questions=questions,
                    model=self.settings.resolved_jev_model or None,
                )
        except Exception as exc:
            raise JevTeacherError(f"TypeSafe Jev request failed: {exc}") from exc
        return _to_dict(response)

    def _ask_openrouter(self, state: dict[str, Any], questions: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.settings.resolved_jev_model,
            "state": state,
            "questions": questions,
        }
        request = urllib.request.Request(
            f"{self.settings.resolved_jev_base_url}/api/alpha/decisions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.resolved_jev_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.settings.jev_timeout_seconds
            ) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:600]
            raise JevTeacherError(f"OpenRouter Jev returned HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise JevTeacherError(f"OpenRouter Jev request failed: {exc}") from exc
