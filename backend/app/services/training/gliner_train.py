from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="AutoLaya GLiNER2 fine-tune runner")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--eval", default="")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=1)
    parser.add_argument("--encoder-lr", type=float, default=1e-5)
    parser.add_argument("--task-lr", type=float, default=5e-4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--lora", action="store_true")
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from gliner2 import AutoExtractor
    from gliner2.training.trainer import ExtractorTrainer, TrainingConfig

    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    print(f"gliner-train: loading {args.base} on {args.device}", flush=True)
    model = AutoExtractor.from_pretrained(args.base)
    config = TrainingConfig(
        output_dir=str(output),
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        encoder_lr=args.encoder_lr,
        task_lr=args.task_lr,
        seed=args.seed,
        eval_strategy="epoch" if args.eval else "no",
        save_best=bool(args.eval),
        save_total_limit=2,
        use_lora=args.lora,
        lora_r=args.lora_r,
        num_workers=2,
    )
    trainer = ExtractorTrainer(model, config)
    print("gliner-train: starting", flush=True)
    summary = trainer.train(train_data=args.data, eval_data=args.eval or None)
    (output / "gliner_train_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    final = output / "final"
    print(f"gliner-train: complete -> {final}", flush=True)
    return 0 if final.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
