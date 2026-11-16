from __future__ import annotations

import csv
import io
import json
from typing import Any

from pydantic import ValidationError

from app.schemas.sample import SampleCreate
from app.schemas.seed import SeedCreate

MAX_IMPORT_ROWS = 5000
JSONL_SUFFIXES = {".jsonl", ".ndjson"}
CSV_SUFFIXES = {".csv"}


def jsonl_template() -> str:
    rows = [
        {
            "state": {"ticket": "I was charged twice this month, please refund the duplicate."},
            "labels": {"team": "billing"},
            "language": "en",
            "difficulty": "easy",
            "heldout": False,
        },
        {
            "state": {"ticket": "生产环境 API 登录后持续返回 500，请尽快处理。"},
            "labels": {"team": "technical"},
            "language": "zh",
            "difficulty": "medium",
            "heldout": False,
        },
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"


def csv_template() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["state", "labels", "language", "difficulty", "heldout"])
    writer.writerow(
        [
            json.dumps(
                {"ticket": "I was charged twice this month, please refund the duplicate."},
                ensure_ascii=False,
            ),
            json.dumps({"team": "billing"}, ensure_ascii=False),
            "en",
            "easy",
            "false",
        ]
    )
    writer.writerow(
        [
            json.dumps(
                {"ticket": "生产环境 API 登录后持续返回 500，请尽快处理。"},
                ensure_ascii=False,
            ),
            json.dumps({"team": "technical"}, ensure_ascii=False),
            "zh",
            "medium",
            "false",
        ]
    )
    return "\ufeff" + buffer.getvalue()


def _parse_object(value: Any, field: str, row_number: int) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Row {row_number}: {field} is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Row {row_number}: {field} must be a JSON object")
        return parsed
    raise ValueError(f"Row {row_number}: {field} must be a JSON object")


def _parse_state(value: Any, row_number: int) -> dict[str, Any]:
    if isinstance(value, dict):
        state = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Row {row_number}: state is not valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError(f"Row {row_number}: state must be a JSON object")
            state = parsed
        else:
            state = {"text": value}
    else:
        raise ValueError(f"Row {row_number}: state is required")
    if not state:
        raise ValueError(f"Row {row_number}: state cannot be empty")
    return state


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _build_sample(
    row: dict[str, Any],
    row_number: int,
    source: str,
    allowed_keys: set[str],
) -> SampleCreate:
    labels = _parse_object(row.get("labels"), "labels", row_number)
    unknown = sorted(set(labels) - allowed_keys)
    if unknown:
        raise ValueError(f"Row {row_number}: unknown question keys: {', '.join(unknown)}")
    meta = _parse_object(row.get("meta"), "meta", row_number)
    heldout = _parse_bool(row.get("heldout", meta.get("heldout", False)))
    if heldout:
        meta["heldout"] = True
    meta["importFormat"] = source
    meta["importRow"] = row_number
    try:
        return SampleCreate(
            state=_parse_state(row.get("state"), row_number),
            labels=labels,
            meta=meta,
            source=source,
            language=str(row.get("language") or "en").strip() or "en",
            difficulty=str(row.get("difficulty") or "medium").strip() or "medium",
        )
    except ValidationError as exc:
        raise ValueError(f"Row {row_number}: {exc.errors()[0]['msg']}") from exc


def parse_sample_file(
    filename: str,
    content: bytes,
    allowed_keys: set[str],
) -> list[SampleCreate]:
    suffix = ""
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[1].lower()
    if suffix not in JSONL_SUFFIXES | CSV_SUFFIXES:
        raise ValueError("Unsupported file type. Upload a .jsonl, .ndjson, or .csv file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("File must be UTF-8 encoded") from exc

    samples: list[SampleCreate] = []
    if suffix in JSONL_SUFFIXES:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Row {line_number}: invalid JSONL") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Row {line_number}: each JSONL line must be an object")
            samples.append(_build_sample(row, line_number, "import-jsonl", allowed_keys))
    else:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "state" not in {
            name.strip() for name in reader.fieldnames if name
        }:
            raise ValueError("CSV must include a state column")
        for row_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            normalized = {str(key).strip(): value for key, value in row.items() if key}
            samples.append(_build_sample(normalized, row_number, "import-csv", allowed_keys))

    if not samples:
        raise ValueError("The file contains no samples")
    if len(samples) > MAX_IMPORT_ROWS:
        raise ValueError(f"At most {MAX_IMPORT_ROWS} samples can be imported at once")
    return samples


def jsonl_seed_template() -> str:
    rows = [
        {
            "state": {"ticket": "I was charged twice this month, please refund the duplicate."},
            "labels": {"team": "billing"},
            "language": "en",
        },
        {
            "state": {"ticket": "生产环境 API 登录后持续返回 500，请尽快处理。"},
            "labels": {"team": "technical"},
            "language": "zh",
        },
    ]
    return "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"


def csv_seed_template() -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["state", "labels", "language"])
    writer.writerow(
        [
            json.dumps(
                {"ticket": "I was charged twice this month, please refund the duplicate."},
                ensure_ascii=False,
            ),
            json.dumps({"team": "billing"}, ensure_ascii=False),
            "en",
        ]
    )
    writer.writerow(
        [
            json.dumps(
                {"ticket": "生产环境 API 登录后持续返回 500，请尽快处理。"},
                ensure_ascii=False,
            ),
            json.dumps({"team": "technical"}, ensure_ascii=False),
            "zh",
        ]
    )
    return "\ufeff" + buffer.getvalue()


def _build_seed(
    row: dict[str, Any],
    row_number: int,
    source: str,
    allowed_keys: set[str],
) -> SeedCreate:
    labels = _parse_object(row.get("labels"), "labels", row_number)
    unknown = sorted(set(labels) - allowed_keys)
    if unknown:
        raise ValueError(f"Row {row_number}: unknown question keys: {', '.join(unknown)}")
    try:
        return SeedCreate(
            state=_parse_state(row.get("state"), row_number),
            labels=labels,
            source=source,
            language=str(row.get("language") or "en").strip() or "en",
        )
    except ValidationError as exc:
        raise ValueError(f"Row {row_number}: {exc.errors()[0]['msg']}") from exc


def parse_seed_file(
    filename: str,
    content: bytes,
    allowed_keys: set[str],
) -> list[SeedCreate]:
    suffix = ""
    if "." in filename:
        suffix = "." + filename.rsplit(".", 1)[1].lower()
    if suffix not in JSONL_SUFFIXES | CSV_SUFFIXES:
        raise ValueError("Unsupported file type. Upload a .jsonl, .ndjson, or .csv file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("File must be UTF-8 encoded") from exc

    seeds: list[SeedCreate] = []
    if suffix in JSONL_SUFFIXES:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Row {line_number}: invalid JSONL") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Row {line_number}: each JSONL line must be an object")
            seeds.append(_build_seed(row, line_number, "import-jsonl", allowed_keys))
    else:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "state" not in {
            name.strip() for name in reader.fieldnames if name
        }:
            raise ValueError("CSV must include a state column")
        for row_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            normalized = {str(key).strip(): value for key, value in row.items() if key}
            seeds.append(_build_seed(normalized, row_number, "import-csv", allowed_keys))

    if not seeds:
        raise ValueError("The file contains no seeds")
    if len(seeds) > MAX_IMPORT_ROWS:
        raise ValueError(f"At most {MAX_IMPORT_ROWS} seeds can be imported at once")
    return seeds
