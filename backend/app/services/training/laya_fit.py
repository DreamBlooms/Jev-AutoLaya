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
    import numpy as np
    from laya.vega import VegaAgent
    from vegaml.ttt import TTTHead

    original_fit = TTTHead.fit
    replacement_count = 0

    def robust_fit(self, features, y_labels):
        nonlocal replacement_count
        values = np.asarray(features, dtype=np.float32)
        finite = np.isfinite(values)
        if not finite.all():
            bad = int(values.size - finite.sum())
            replacement_count += bad
            print(f"fit: warning: replacing {bad} non-finite feature values", flush=True)
            values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        return original_fit(self, values, y_labels)

    TTTHead.fit = robust_fit
    min_calibrated = VegaAgent.min_rows(questions, calibrate=True)
    min_heads = VegaAgent.min_rows(questions, calibrate=False)
    if len(rows) < min_heads:
        raise SystemExit(
            f"fit needs at least {min_heads} labelled rows for these questions; got {len(rows)}. "
            "Add more labelled rows or use fine-tune instead."
        )
    print(f"fit: loading Laya agent for {len(rows)} rows on {args.device}", flush=True)
    agent = laya.Agent(**kwargs)
    heads_only = len(rows) < min_calibrated
    print(
        f"fit: fitting heads only (calibration needs at least {min_calibrated} rows)"
        if heads_only
        else "fit: fitting heads and calibration",
        flush=True,
    )
    report = agent.fit(rows, questions=questions, calibrate=not heads_only)
    if replacement_count:
        note = (
            f"Replaced {replacement_count} non-finite feature values before fitting heads. "
            "Model quality may be reduced; try a different device or a smaller/cleaner dataset."
        )
        report["non_finite_features_replaced"] = replacement_count
        report["warning"] = f"{report.get('warning', '')} {note}".strip()
    if heads_only:
        report["fit_mode"] = "heads_only"
        report["calibrated"] = False
        report["min_rows_calibrated"] = min_calibrated
        report["warning"] = (
            f"Only {len(rows)} labelled rows were available; Fit calibrated on at least "
            f"{min_calibrated}. Heads were fitted on all rows without calibration. "
            "Add more rows for calibrated confidence."
        )
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
