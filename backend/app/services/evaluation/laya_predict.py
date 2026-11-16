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


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoLaya Laya prediction runner")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--calibration", default="")
    parser.add_argument("--backbone", default="")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--mode", choices=["base", "checkpoint", "fit"], default="base")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    import laya

    rows = read_jsonl(Path(args.data))
    if args.limit > 0:
        rows = rows[: args.limit]
    device = None if args.device == "auto" else ("cuda" if args.device == "rocm" else args.device)
    kwargs: dict[str, Any] = {}
    if device:
        kwargs["device"] = device
    print(f"laya-eval: loading {args.model} ({args.mode}) on {args.device}", flush=True)
    if args.mode == "fit":
        if args.backbone:
            kwargs["backbone"] = args.backbone
        agent = laya.Agent(vegaml=args.model or True, **kwargs)
        if args.calibration:
            agent.load_calibration(args.calibration)
    else:
        if args.mode == "base" and args.calibration:
            kwargs["calibration"] = args.calibration
        agent = laya.load(args.model, **kwargs)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for index, row in enumerate(rows, start=1):
            started = time.perf_counter()
            result: dict[str, Any] = {}
            error = None
            try:
                result = agent.predict(row["state"], row["questions"])
            except Exception as exc:
                error = str(exc)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            payload = {
                "index": index - 1,
                "id": row.get("id"),
                "answers": result.get("answers") or {},
                "routing": result.get("routing"),
                "usage": result.get("usage"),
                "elapsed_ms": elapsed_ms,
                "error": error,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            if index % 20 == 0:
                print(f"laya-eval: {index}/{len(rows)}", flush=True)
    print("laya-eval: complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
