from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _schema(classification: dict[str, Any]) -> dict[str, Any]:
    labels = classification.get("labels") or []
    descriptions = classification.get("label_descriptions")
    prompt = classification.get("prompt")
    spec: dict[str, Any] = {
        "labels": descriptions if isinstance(descriptions, dict) and descriptions else labels
    }
    if prompt:
        spec["prompt"] = prompt
    if classification.get("multi_label"):
        spec["multi_label"] = True
    return spec


def _answer(classification: dict[str, Any], result: Any) -> dict[str, Any]:
    labels = [str(label) for label in classification.get("labels") or []]
    question_type = classification.get("type")
    labels_lower = [label.lower() for label in labels]
    if isinstance(result, dict):
        value = result.get("value", result.get("label"))
        confidence = result.get("confidence")
        probabilities = result.get("probabilities") or {}
    else:
        value = result
        confidence = 1.0
        probabilities = {}
    if isinstance(value, list):
        value = value[0] if value else None
    if question_type == "noul" or "yes" in labels_lower or "no" in labels_lower:
        probability = None
        for key, raw in probabilities.items():
            if str(key).lower() == "yes":
                probability = float(raw)
                break
        if probability is None:
            probability = (
                float(confidence or 1.0)
                if str(value).lower() == "yes"
                else 1.0 - float(confidence or 1.0)
            )
        return {
            "noul": probability,
            "confidence": float(confidence or probability),
            "probabilities": {"yes": probability, "no": 1.0 - probability},
        }
    if question_type == "score" or (
        labels and all(label.lstrip("-").isdigit() for label in labels)
    ):
        index = labels.index(str(value)) if str(value) in labels else 0
        confidence = float(confidence or 1.0)
        if not probabilities and labels:
            probabilities = {
                label: (confidence if i == index else (1.0 - confidence) / max(1, len(labels) - 1))
                for i, label in enumerate(labels)
            }
        return {
            "score": index,
            "confidence": confidence,
            "probabilities": {
                str(i): float(probabilities.get(label, 0.0)) for i, label in enumerate(labels)
            },
        }
    confidence = float(confidence or 1.0)
    if not probabilities and labels:
        probabilities = {label: 0.0 for label in labels}
        probabilities[str(value)] = confidence
        for label in labels:
            if label != str(value):
                probabilities[label] = (1.0 - confidence) / max(1, len(labels) - 1)
    return {
        "choice": str(value),
        "confidence": confidence,
        "probabilities": {str(key): float(raw) for key, raw in probabilities.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoLaya GLiNER prediction runner")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    import torch
    from gliner2 import AutoExtractor

    rows = read_jsonl(Path(args.data))
    if args.limit > 0:
        rows = rows[: args.limit]
    device = args.device
    if device == "rocm":
        device = "cuda"
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"gliner-eval: loading {args.model} on {device}", flush=True)
    model = AutoExtractor.from_pretrained(args.model)
    model.to(torch.device(device))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for index, row in enumerate(rows, start=1):
            started = time.perf_counter()
            answers: dict[str, Any] = {}
            error = None
            try:
                classifications = (row.get("output") or {}).get("classifications") or []
                schema = {item["task"]: _schema(item) for item in classifications}
                result = model.classify_text(
                    row["input"],
                    schema,
                    include_confidence=True,
                )
                for item in classifications:
                    task = item["task"]
                    if task in result:
                        answers[task] = _answer(item, result[task])
            except Exception as exc:
                error = str(exc)
            handle.write(
                json.dumps(
                    {
                        "index": index - 1,
                        "id": row.get("id"),
                        "answers": answers,
                        "elapsed_ms": (time.perf_counter() - started) * 1000.0,
                        "error": error,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            handle.flush()
            if index % 20 == 0:
                print(f"gliner-eval: {index}/{len(rows)}", flush=True)
    print("gliner-eval: complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
