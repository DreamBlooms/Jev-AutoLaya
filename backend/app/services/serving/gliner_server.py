from __future__ import annotations

import argparse
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


def state_text(state: Any) -> str:
    if isinstance(state, str):
        return state
    if not isinstance(state, dict):
        return json.dumps(state, ensure_ascii=False)
    if set(state) == {"text"}:
        return str(state["text"])
    lines = []
    for key, value in state.items():
        rendered = (
            json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        )
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines)


def _task_spec(question: dict[str, Any]) -> dict[str, Any]:
    question_type = question.get("type")
    criteria = question.get("criteria")
    spec: dict[str, Any] = {}
    if question_type == "choice" and isinstance(criteria, dict):
        spec["labels"] = criteria
    elif question_type == "noul":
        spec["labels"] = ["yes", "no"]
    elif question_type == "score":
        spec["labels"] = (
            list(criteria)
            if isinstance(criteria, list) and criteria
            else [str(index) for index in range(6)]
        )
    else:
        spec["labels"] = list(criteria) if isinstance(criteria, list) else []
    if question.get("instructions"):
        spec["prompt"] = question["instructions"]
    return spec


def _labels_for(question: dict[str, Any]) -> list[str]:
    labels = _task_spec(question).get("labels") or []
    return list(labels) if isinstance(labels, dict) else [str(label) for label in labels]


def _answer(
    question_type: str,
    result: Any,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    labels = labels or []
    if isinstance(result, dict):
        value = result.get("value", result.get("label"))
        confidence = float(result.get("confidence") or 1.0)
        probabilities = result.get("probabilities") or {}
    else:
        value = result
        confidence = 1.0
        probabilities = {}
    if isinstance(value, list):
        value = value[0] if value else None
    if question_type == "noul":
        p_true = None
        for key, raw in probabilities.items():
            if str(key).lower() in {"yes", "true"}:
                p_true = float(raw)
                break
        if p_true is None:
            p_true = confidence if str(value).lower() == "yes" else 1.0 - confidence
        return {
            "type": "noul",
            "noul": p_true,
            "confidence": confidence,
            "probabilities": {"yes": p_true, "no": 1.0 - p_true},
        }
    if question_type == "score":
        if not labels:
            labels = [str(key) for key in probabilities]
        if str(value) in labels:
            score = labels.index(str(value))
        else:
            try:
                score = int(value)
            except (TypeError, ValueError):
                score = 0
        if not labels:
            labels = [str(i) for i in range(max(1, score + 1))]
        return {
            "type": "score",
            "score": score,
            "confidence": confidence,
            "probabilities": {
                str(index): (
                    float(probabilities.get(label, 0.0))
                    if probabilities
                    else (
                        confidence
                        if index == score
                        else (1.0 - confidence) / max(1, len(labels) - 1)
                    )
                )
                for index, label in enumerate(labels)
            },
        }
    if not probabilities and labels:
        probabilities = {label: 0.0 for label in labels}
        probabilities[str(value)] = confidence
        for label in labels:
            if label != str(value):
                probabilities[label] = (1.0 - confidence) / max(1, len(labels) - 1)
    return {
        "type": "choice",
        "choice": str(value),
        "confidence": confidence,
        "probabilities": {str(key): float(raw) for key, raw in probabilities.items()},
    }


def create_app(model: str, device: str) -> FastAPI:
    import torch
    from gliner2 import AutoExtractor

    target_device = device
    if target_device == "rocm":
        target_device = "cuda"
    if target_device == "auto":
        target_device = "cuda" if torch.cuda.is_available() else "cpu"
    extractor = AutoExtractor.from_pretrained(model)
    extractor.to(torch.device(target_device))
    app = FastAPI(title="AutoLaya GLiNER server")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "model": model, "device": target_device}

    @app.post("/v1/classify")
    async def classify(request: Request) -> JSONResponse:
        body = await request.json()
        text = body.get("text")
        schema = body.get("schema") or body.get("tasks")
        if not isinstance(text, str) or not isinstance(schema, dict) or not schema:
            raise HTTPException(status_code=422, detail="text and schema are required")
        try:
            result = extractor.classify_text(
                text,
                schema,
                threshold=float(body.get("threshold", 0.5)),
                include_confidence=True,
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": {"message": str(exc)}})
        return JSONResponse({"model": model, "result": result})

    @app.post("/v1/classify/batch")
    async def classify_batch(request: Request) -> JSONResponse:
        body = await request.json()
        texts = body.get("texts")
        schema = body.get("schema") or body.get("tasks")
        if not isinstance(texts, list) or not isinstance(schema, dict) or not schema:
            raise HTTPException(status_code=422, detail="texts and schema are required")
        try:
            results = extractor.batch_classify_text(
                texts,
                schema,
                batch_size=int(body.get("batchSize", 8)),
                threshold=float(body.get("threshold", 0.5)),
                include_confidence=True,
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": {"message": str(exc)}})
        return JSONResponse({"model": model, "results": results})

    @app.post("/v1/systemone")
    async def system_one(request: Request) -> JSONResponse:
        body = await request.json()
        state = body.get("state")
        questions = body.get("questions")
        if state is None or not isinstance(questions, dict) or not questions:
            raise HTTPException(status_code=422, detail="state and questions are required")
        schema = {key: _task_spec(question) for key, question in questions.items()}
        try:
            result = extractor.classify_text(
                state_text(state),
                schema,
                include_confidence=True,
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": {"message": str(exc)}})
        answers = {
            key: _answer(
                questions[key].get("type", "choice"),
                result.get(key),
                _labels_for(questions[key]),
            )
            for key in questions
            if key in result
        }
        return JSONResponse({"model": body.get("model") or model, "answers": answers})

    @app.post("/v1/systemone/batch")
    async def system_one_batch(request: Request) -> JSONResponse:
        body = await request.json()
        states = body.get("states")
        questions = body.get("questions")
        if not isinstance(states, list) or not isinstance(questions, dict) or not questions:
            raise HTTPException(status_code=422, detail="states and questions are required")
        schema = {key: _task_spec(question) for key, question in questions.items()}
        try:
            results = extractor.batch_classify_text(
                [state_text(state) for state in states],
                schema,
                batch_size=int(body.get("batchSize", 8)),
                include_confidence=True,
            )
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": {"message": str(exc)}})
        outputs = [
            {
                "answers": {
                    key: _answer(
                        questions[key].get("type", "choice"),
                        result.get(key),
                        _labels_for(questions[key]),
                    )
                    for key in questions
                    if key in result
                }
            }
            for result in results
        ]
        return JSONResponse({"model": model, "results": outputs})

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8101)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(create_app(args.model, args.device), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
