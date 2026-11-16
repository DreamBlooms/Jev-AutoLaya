from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.core.config import get_settings


class LLMError(RuntimeError):
    pass


def chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def build_chat_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    think_budget: int | None = None,
    think_level: str | None = None,
    json_mode: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    if think_budget is not None and think_budget > 0:
        payload["reasoning"] = {"max_tokens": think_budget}
    if think_level:
        payload["reasoning_effort"] = think_level
    return payload


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        think_budget: int | None = None,
        think_level: str | None = None,
        timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
        self.think_budget = think_budget
        self.think_level = think_level
        self.timeout = timeout or settings.llm_timeout_seconds
        if not self.api_key:
            raise LLMError("LLM_API_KEY is not configured")
        if not self.model:
            raise LLMError("LLM_MODEL is not configured")
        self._client = httpx.Client(timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    @property
    def endpoint(self) -> str:
        return chat_completions_url(self.base_url)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = True,
    ) -> str:
        payload = build_chat_payload(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=max_tokens or self.max_tokens,
            think_budget=self.think_budget,
            think_level=self.think_level,
            json_mode=json_mode,
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error = ""
        for attempt in range(3):
            try:
                response = self._client.post(self.endpoint, json=payload, headers=headers)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    text = response.text[:800]
                    raise LLMError(f"LLM returned HTTP {response.status_code}: {text}")
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise LLMError("LLM returned an empty response")
                return content
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                last_error = str(exc)
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(f"LLM request failed: {last_error}") from exc
        raise LLMError(f"LLM request failed: {last_error}")

    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        content = self.chat(messages, **kwargs)
        return parse_json_content(content)


def parse_json_content(content: str) -> Any:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
        if not starts:
            raise LLMError("LLM response did not contain JSON") from None
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end <= start:
            raise LLMError("LLM response contained incomplete JSON") from None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"Could not parse LLM JSON: {exc}") from exc
