from __future__ import annotations

import math
from typing import Any


def expected_value(row: dict[str, Any], key: str) -> Any:
    expected = row.get("expected")
    if isinstance(expected, dict) and key in expected:
        return expected[key]
    gold = row.get("gold")
    if not isinstance(gold, dict) or key not in gold:
        return None
    answer = gold[key]
    if not isinstance(answer, dict):
        return answer
    if "choice" in answer:
        return answer["choice"]
    if "noul" in answer:
        return float(answer["noul"]) >= 0.5
    return answer.get("score")


def _is_correct(question_type: str, expected: Any, answer: dict[str, Any]) -> bool:
    if question_type == "choice":
        return answer.get("choice") == expected
    if question_type == "noul":
        value = answer.get("noul")
        if value is None:
            return False
        return bool(float(value) >= 0.5) == bool(expected)
    if question_type == "score":
        try:
            return int(round(float(answer.get("score")))) == int(round(float(expected)))
        except (TypeError, ValueError):
            return False
    return False


def _confidence(question_type: str, expected: Any, answer: dict[str, Any]) -> float | None:
    if question_type == "choice":
        probabilities = answer.get("probabilities")
        choice = answer.get("choice")
        if isinstance(probabilities, dict) and choice in probabilities:
            try:
                return max(0.0, min(1.0, float(probabilities[choice])))
            except (TypeError, ValueError):
                return None
        value = answer.get("confidence")
        return float(value) if isinstance(value, (int, float)) else None
    if question_type == "noul":
        value = answer.get("noul")
        if value is None:
            return None
        probability = max(0.0, min(1.0, float(value)))
        return probability if bool(expected) else 1.0 - probability
    value = answer.get("confidence")
    return float(value) if isinstance(value, (int, float)) else None


def _brier(question_type: str, expected: Any, answer: dict[str, Any]) -> float | None:
    if question_type == "noul":
        value = answer.get("noul")
        if value is None:
            return None
        probability = max(0.0, min(1.0, float(value)))
        target = 1.0 if bool(expected) else 0.0
        return (probability - target) ** 2
    probabilities = answer.get("probabilities")
    if isinstance(probabilities, dict) and probabilities:
        total = 0.0
        for label, probability in probabilities.items():
            try:
                value = float(probability)
            except (TypeError, ValueError):
                continue
            target = 1.0 if str(label) == str(expected) else 0.0
            total += (value - target) ** 2
        return total
    if question_type == "score":
        try:
            return (float(answer.get("score")) - float(expected)) ** 2
        except (TypeError, ValueError):
            return None
    return None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((percentile / 100) * (len(ordered) - 1))))
    return round(ordered[index], 3)


def _macro_f1(expected: list[Any], predicted: list[Any]) -> float | None:
    labels = set(expected) | set(predicted)
    if not labels:
        return None
    scores = []
    for label in labels:
        tp = sum(1 for e, p in zip(expected, predicted, strict=False) if e == label and p == label)
        fp = sum(1 for e, p in zip(expected, predicted, strict=False) if e != label and p == label)
        fn = sum(1 for e, p in zip(expected, predicted, strict=False) if e == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def aggregate(
    rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    probabilities_reliable: bool = True,
) -> dict[str, Any]:
    by_question: dict[str, dict[str, Any]] = {}
    latencies = [float(item.get("elapsed_ms") or 0.0) for item in predictions]
    errors = sum(1 for item in predictions if item.get("error"))
    for index, row in enumerate(rows):
        prediction = predictions[index] if index < len(predictions) else {}
        answers = prediction.get("answers") if isinstance(prediction, dict) else {}
        answers = answers or {}
        for key, question in (row.get("questions") or {}).items():
            question_type = str(question.get("type", "choice"))
            expected = expected_value(row, key)
            if expected is None:
                continue
            answer = answers.get(key) if isinstance(answers, dict) else None
            answer = answer if isinstance(answer, dict) else {}
            entry = by_question.setdefault(
                key,
                {
                    "type": question_type,
                    "n": 0,
                    "correct": 0,
                    "expected": [],
                    "predicted": [],
                    "abs_errors": [],
                    "confidences": [],
                    "outcomes": [],
                    "brier": [],
                    "coverage": [],
                    "abstain": [],
                },
            )
            entry["n"] += 1
            correct = _is_correct(question_type, expected, answer)
            entry["correct"] += int(correct)
            entry["outcomes"].append((float(correct), _confidence(question_type, expected, answer)))
            brier = _brier(question_type, expected, answer)
            if brier is not None:
                entry["brier"].append(brier)
            if question_type == "choice":
                entry["expected"].append(expected)
                entry["predicted"].append(answer.get("choice"))
            elif question_type == "noul":
                entry["expected"].append(bool(expected))
                entry["predicted"].append(bool(float(answer.get("noul") or 0) >= 0.5))
            else:
                try:
                    error = abs(float(answer.get("score")) - float(expected))
                except (TypeError, ValueError):
                    error = math.inf
                entry["abs_errors"].append(error)
                entry["expected"].append(expected)
                entry["predicted"].append(answer.get("score"))
            confidence = _confidence(question_type, expected, answer)
            if confidence is not None:
                entry["confidences"].append(confidence)
            prediction_set = answer.get("prediction_set")
            if isinstance(prediction_set, list):
                entry["coverage"].append(len(prediction_set))
            if "abstain" in answer:
                entry["abstain"].append(bool(answer.get("abstain")))

    metrics = {}
    for key, entry in by_question.items():
        n = entry["n"]
        accuracy = entry["correct"] / n if n else None
        ece = _ece(entry["outcomes"])
        metrics[key] = {
            "type": entry["type"],
            "n": n,
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
            "macro_f1": round(_macro_f1(entry["expected"], entry["predicted"]), 4)
            if entry["type"] in {"choice", "noul"}
            else None,
            "mae": round(sum(entry["abs_errors"]) / len(entry["abs_errors"]), 4)
            if entry["abs_errors"]
            else None,
            "ece": round(ece, 4) if ece is not None else None,
            "brier": (
                round(sum(entry["brier"]) / len(entry["brier"]), 4)
                if probabilities_reliable and entry["brier"]
                else None
            ),
            "probability_fidelity": "full" if probabilities_reliable else "confidence_only",
            "coverage": round(sum(entry["coverage"]) / len(entry["coverage"]), 3)
            if entry["coverage"]
            else None,
            "abstain_rate": round(sum(entry["abstain"]) / len(entry["abstain"]), 4)
            if entry["abstain"]
            else None,
        }
    accuracies = [item["accuracy"] for item in metrics.values() if item["accuracy"] is not None]
    return {
        "n": len(rows),
        "questions": metrics,
        "accuracy": round(sum(accuracies) / len(accuracies), 4) if accuracies else None,
        "errors": errors,
        "latency_p50_ms": _percentile(latencies, 50),
        "latency_p95_ms": _percentile(latencies, 95),
    }


def _ece(outcomes: list[tuple[float, float | None]], bins: int = 10) -> float | None:
    usable = [(correct, confidence) for correct, confidence in outcomes if confidence is not None]
    if not usable:
        return None
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for correct, confidence in usable:
        index = min(bins - 1, max(0, int(confidence * bins)))
        buckets[index].append((correct, confidence))
    total = len(usable)
    value = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        accuracy = sum(item[0] for item in bucket) / len(bucket)
        confidence = sum(item[1] for item in bucket) / len(bucket)
        value += abs(accuracy - confidence) * len(bucket) / total
    return value


def markdown_report(run: dict[str, Any]) -> str:
    lines = [f"# Evaluation {run.get('id', '')}", ""]
    lines.append(f"Snapshot: `{run.get('snapshot_id', '')}`")
    lines.append("")
    model_info = run.get("model_info") or {}
    for model, result in (run.get("models") or {}).items():
        info = model_info.get(model) or {}
        title = (info.get("artifact") or {}).get("name") or model
        lines.extend([f"## {title}", ""])
        lines.append(f"- Key: `{model}`")
        if info.get("role"):
            lines.append(f"- Role: {info.get('role')}")
        if info.get("target"):
            lines.append(f"- Target: {info.get('target')}")
        if info.get("source"):
            lines.append(f"- Source: `{info.get('source')}`")
        artifact = info.get("artifact") or {}
        if artifact.get("createdAt"):
            lines.append(f"- Artifact created: {artifact.get('createdAt')}")
        lines.append(
            f"- N: {result.get('n')}  Accuracy: {result.get('accuracy')}  "
            f"P50: {result.get('latency_p50_ms')} ms  P95: {result.get('latency_p95_ms')} ms"
        )
        lines.append("")
        lines.append(
            "| Question | Type | N | Accuracy | Macro F1 | MAE | ECE | Brier | Coverage | Abstain |"
        )
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for key, item in (result.get("questions") or {}).items():
            lines.append(
                f"| {key} | {item.get('type')} | {item.get('n')} | {item.get('accuracy')} | "
                f"{item.get('macro_f1')} | {item.get('mae')} | {item.get('ece')} | "
                f"{item.get('brier')} | {item.get('coverage')} | {item.get('abstain_rate')} |"
            )
        lines.append("")
    return "\n".join(lines)
