from __future__ import annotations

import json
import re
from typing import Any

from app.models import Project, Question, SeedSample

LANGUAGE_NAMES = {"zh": "Simplified Chinese", "en": "English"}
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
KNOWN_PLACEHOLDERS = {
    "project_name",
    "project_domain",
    "language",
    "count",
    "difficulty",
    "negative_ratio",
    "schema_json",
    "seeds_json",
    "sample_shape",
    "label_rule",
    "label_instruction",
    "balancing",
    "negative_instruction",
    "default_system",
    "default_user",
    "custom_prompt",
}

DEFAULT_SYSTEM_TEMPLATE = (
    "You are a careful synthetic data generator for a decision-model training pipeline. "
    "You write realistic domain examples. You only produce labels when the user asks for "
    "them, and then they must be consistent weak labels for human review. Output JSON only."
)

DEFAULT_USER_TEMPLATE = """
Domain: {{project_name}}
Domain description: {{project_domain}}

Decision schema:
{{schema_json}}

Seed state examples:
{{seeds_json}}

Generate exactly {{count}} new, realistic domain states in {{language}}.
Return one JSON object with a "samples" array. Each element must be:
{{sample_shape}}

Rules:
- "state" must be a non-empty JSON object, not a string.
- Preserve the field names and structure used by the seed states when they fit the domain.
- If the seeds use a single text field, use a single descriptive field such as "text" or "ticket".
- {{label_rule}}
- Vary length, tone, vocabulary, and specificity.
- Use difficulty mix: {{difficulty}}.
- {{balancing}}
- {{negative_instruction}}
- {{label_instruction}}
- Avoid exact duplicates of the seeds or of each other.
- The examples must be usable by a human reviewer without external context.
""".strip()


class PromptTemplateError(ValueError):
    pass


def question_schema(questions: list[Question]) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    for question in questions:
        item: dict[str, Any] = {
            "type": question.type,
            "instructions": question.instructions,
        }
        if question.type == "choice":
            item["criteria"] = question.criteria or {}
        elif question.type == "score" and question.criteria:
            item["criteria"] = question.criteria
        schema[question.key] = item
    return schema


def validate_prompt_templates(*templates: str | None) -> None:
    unknown: set[str] = set()
    for template in templates:
        if template:
            unknown.update(set(PLACEHOLDER_RE.findall(template)) - KNOWN_PLACEHOLDERS)
    if unknown:
        raise PromptTemplateError("Unknown prompt placeholders: " + ", ".join(sorted(unknown)))


def _render_template(template: str, context: dict[str, str]) -> str:
    validate_prompt_templates(template)
    return PLACEHOLDER_RE.sub(lambda match: context[match.group(1)], template)


def prompt_template_defaults() -> dict[str, Any]:
    return {
        "system": DEFAULT_SYSTEM_TEMPLATE,
        "user": DEFAULT_USER_TEMPLATE,
        "placeholders": sorted(KNOWN_PLACEHOLDERS),
    }


def build_messages(
    *,
    project: Project,
    questions: list[Question],
    seeds: list[SeedSample],
    count: int,
    language: str,
    difficulty: dict[str, float],
    negative_ratio: float,
    label_balanced: bool,
    label_with_llm: bool = False,
    custom_prompt: str | None = None,
    system_prompt_template: str | None = None,
    user_prompt_template: str | None = None,
) -> list[dict[str, str]]:
    language_name = LANGUAGE_NAMES.get(language, language)
    schema = question_schema(questions)
    seed_states = [{"state": seed.state, "language": seed.language} for seed in seeds[:12]]
    difficulty_text = (
        ", ".join(
            f"{name} {round(value * 100)}%" for name, value in difficulty.items() if value > 0
        )
        or "medium 100%"
    )
    balancing = ""
    if label_balanced:
        balancing = (
            "Balance the examples across the decision labels and score levels as evenly as "
            "the domain allows. Keep labels out of the state object itself."
        )
    sample_shape = (
        '{"state": {...}, "language": "' + language + '", '
        '"difficulty": "easy|medium|hard", "labels": {...}}'
        if label_with_llm
        else '{"state": {...}, "language": "' + language + '", "difficulty": "easy|medium|hard"}'
    )
    label_instruction = ""
    if label_with_llm:
        label_instruction = """
- When labels are requested, each element must also carry a "labels" object.
- Label every question in the schema exactly once.
- Choice answer: one of the criteria keys, or an object like
  {"choice": "label", "confidence": 0.0-1.0}.
- Noul answer: true/false, a probability 0.0-1.0, or an object like
  {"noul": 0.8, "confidence": 0.0-1.0}.
- Score answer: an integer level index from 0 to (number of levels - 1),
  optionally with confidence.
- Labels must be consistent with the state. Do not put labels inside the state.
- These labels are weak synthetic labels; a human reviewer will verify them.
""".strip()
    label_rule = (
        "Use the requested labels object for every question."
        if label_with_llm
        else "Do not output labels, gold answers, probabilities, explanations, or markdown."
    )
    negative = ""
    if negative_ratio > 0:
        negative = (
            f"About {round(negative_ratio * 100)}% should be difficult or adversarial: "
            "ambiguous wording, mixed intents, negation, missing context, noise, or examples "
            "close to a decision boundary. They still must be plausible."
        )
    custom = (custom_prompt or "").strip()
    context = {
        "project_name": project.name,
        "project_domain": project.domain or "Not provided",
        "language": language_name,
        "count": str(count),
        "difficulty": difficulty_text,
        "negative_ratio": str(negative_ratio),
        "schema_json": json.dumps(schema, ensure_ascii=False, indent=2),
        "seeds_json": json.dumps(seed_states, ensure_ascii=False, indent=2),
        "sample_shape": sample_shape,
        "label_rule": label_rule,
        "label_instruction": label_instruction,
        "balancing": balancing,
        "negative_instruction": negative,
        "default_system": DEFAULT_SYSTEM_TEMPLATE,
        "default_user": "",
        "custom_prompt": custom,
    }
    context["default_user"] = _render_template(DEFAULT_USER_TEMPLATE, context)
    validate_prompt_templates(system_prompt_template, user_prompt_template)
    system = (
        _render_template(system_prompt_template, context)
        if system_prompt_template and system_prompt_template.strip()
        else context["default_system"]
    )
    user = (
        _render_template(user_prompt_template, context)
        if user_prompt_template and user_prompt_template.strip()
        else context["default_user"]
    )
    template_text = (system_prompt_template or "") + (user_prompt_template or "")
    if custom and "custom_prompt" not in PLACEHOLDER_RE.findall(template_text):
        user += (
            "\n\nAdditional operator instructions (must not change the required JSON shape "
            "or the decision schema):\n" + custom
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
