from __future__ import annotations

import argparse
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse


def create_app(
    model: str,
    calibration: str,
    device: str,
    api_key: str,
    mode: str = "checkpoint",
    backbone: str = "",
) -> FastAPI:
    import laya

    kwargs: dict[str, Any] = {}
    if device and device != "auto":
        kwargs["device"] = "cuda" if device == "rocm" else device
    if mode == "fit":
        if backbone:
            kwargs["backbone"] = backbone
        agent = laya.Agent(vegaml=model or True, **kwargs)
        if calibration:
            agent.load_calibration(calibration)
    else:
        if mode == "base" and calibration:
            kwargs["calibration"] = calibration
        agent = laya.load(model, **kwargs)

    app = FastAPI(title="AutoLaya Laya server")

    def authorize(authorization: str | None) -> None:
        if not api_key:
            return
        if authorization != f"Bearer {api_key}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/health")
    def health(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if api_key and authorization != f"Bearer {api_key}":
            return {"status": "ok"}
        return {"status": "ok", "model": model, "calibrated": bool(calibration)}

    @app.post("/v1/systemone")
    async def system_one(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        authorize(authorization)
        body = await request.json()
        state = body.get("state")
        questions = body.get("questions")
        if state is None or not isinstance(questions, dict) or not questions:
            raise HTTPException(status_code=422, detail="state and questions are required")
        try:
            result = agent.predict(state, questions)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": {"message": str(exc)}})
        result = dict(result)
        result["model"] = body.get("model") or model
        return JSONResponse(result)

    @app.post("/v1/systemone/batch")
    async def system_one_batch(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        authorize(authorization)
        body = await request.json()
        states = body.get("states")
        questions = body.get("questions")
        if not isinstance(states, list) or not isinstance(questions, dict) or not questions:
            raise HTTPException(status_code=422, detail="states and questions are required")
        try:
            results = agent.predict_batch(states, questions)
        except Exception as exc:
            return JSONResponse(status_code=500, content={"error": {"message": str(exc)}})
        return JSONResponse(
            {
                "results": results,
                "total_usage": {
                    key: sum(int((result.get("usage") or {}).get(key) or 0) for result in results)
                    for key in ("input_tokens", "output_tokens")
                },
                "model": body.get("model") or model,
            }
        )

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--calibration", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--api-key", default="")
    parser.add_argument("--mode", choices=["base", "checkpoint", "fit"], default="checkpoint")
    parser.add_argument("--backbone", default="")
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(
        create_app(
            args.model,
            args.calibration,
            args.device,
            args.api_key,
            args.mode,
            args.backbone,
        ),
        host=args.host,
        port=args.port,
        log_level=os.environ.get("LAYA_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
