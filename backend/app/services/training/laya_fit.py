from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Fit Laya heads and calibration on AutoLaya JSONL")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--model", default="")
    parser.add_argument("--backbone", default="")
    args = parser.parse_args()

    import laya

    rows = read_jsonl(Path(args.data))
    if not rows:
        raise SystemExit("No rows to fit")
    questions = {}
    for row in rows:
        for key, question in (row.get("questions") or {}).items():
            questions.setdefault(key, question)
    if not questions:
        raise SystemExit("Rows do not contain a questions schema")

    kwargs: dict[str, Any] = {"vegaml": args.model or True}
    if args.backbone:
        kwargs["backbone"] = args.backbone
    if args.device and args.device != "auto":
        kwargs["device"] = args.device
    print(f"fit: loading Laya agent for {len(rows)} rows on {args.device}", flush=True)
    agent = laya.Agent(**kwargs)
    print("fit: fitting heads and calibration", flush=True)
    report = agent.fit(rows, questions=questions)
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    agent.save_calibration(str(output))
    (output / "fit_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("fit: complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
