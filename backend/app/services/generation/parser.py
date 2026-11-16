from __future__ import annotations

import json
from typing import Any

from app.services.llm.openai_compat import LLMError

DIFFICULTIES = {"easy", "medium", "hard"}


def _text_size(state: dict[str, Any]) -> int:
    return len(json.dumps(state, ensure_ascii=False))


def parse_states(
    payload: Any,
    *,
    language: str,
    default_difficulty: str = "medium",
    max_state_chars: int = 20000,
) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        items = payload.get("samples") or payload.get("states") or payload.get("items")
    else:
        items = payload
    if not isinstance(items, list):
        raise LLMError("Generation response must contain a samples array")

    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_state = item.get("state") if isinstance(item.get("state"), dict) else None
        if raw_state is None:
            raw_state = {
                key: value
                for key, value in item.items()
                if key not in {"language", "difficulty", "labels", "gold", "expected"}
            }
        if not raw_state:
            continue
        if _text_size(raw_state) > max_state_chars:
            continue
        has_text = any(
            isinstance(value, str) and len(value.strip()) >= 3 for value in raw_state.values()
        )
        if not has_text:
            continue
        fingerprint = json.dumps(raw_state, ensure_ascii=False, sort_keys=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        difficulty = str(item.get("difficulty") or default_difficulty).lower()
        if difficulty not in DIFFICULTIES:
            difficulty = default_difficulty
        item_language = str(item.get("language") or language)
        labels = item.get("labels") if isinstance(item.get("labels"), dict) else {}
        output.append(
            {
                "state": raw_state,
                "language": item_language,
                "difficulty": difficulty,
                "labels": labels,
            }
        )
    return output
