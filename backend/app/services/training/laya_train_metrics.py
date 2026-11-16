from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Run laya-train and save training metrics")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--eval", default="")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--micro-batch", type=int, default=8)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--encoder-lr", type=float, default=2.5e-5)
    parser.add_argument("--head-lr", type=float, default=1e-4)
    parser.add_argument("--loss", choices=["rlcd", "soft-ce"], default="rlcd")
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--shuffle-options", action="store_true")
    parser.add_argument("--freeze-encoder", action="store_true")
    parser.add_argument("--target-error", type=float, default=0.1)
    parser.add_argument("--min-abstain-n", type=int, default=10)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-len", type=int, default=None)
    parser.add_argument("--head-max-len", type=int, default=None)
    args = parser.parse_args()

    import torch
    from laya.train import TrainConfig, finetune
    from torch.optim.lr_scheduler import CosineAnnealingLR

    class RecordingCosine(CosineAnnealingLR):
        instances: list[RecordingCosine] = []

        def __init__(self, *init_args: Any, **init_kwargs: Any) -> None:
            self.history: list[list[float]] = []
            self.__class__.instances.append(self)
            super().__init__(*init_args, **init_kwargs)

        def step(self, *step_args: Any, **step_kwargs: Any) -> Any:
            result = super().step(*step_args, **step_kwargs)
            self.history.append([float(value) for value in self.get_last_lr()])
            return result

    torch.optim.lr_scheduler.CosineAnnealingLR = RecordingCosine
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    config = TrainConfig(
        epochs=args.epochs,
        micro_batch=args.micro_batch,
        grad_accum=args.grad_accum,
        encoder_lr=args.encoder_lr,
        head_lr=args.head_lr,
        loss=args.loss,
        label_smoothing=args.label_smoothing,
        shuffle_options=("choice",) if args.shuffle_options else (),
        freeze_encoder=args.freeze_encoder,
        seed=args.seed,
        max_len=args.max_len,
        head_max_len=args.head_max_len,
        eval_data=args.eval or None,
        target_error=args.target_error,
        min_abstain_n=args.min_abstain_n,
        log_every=10,
    )
    summary = finetune(
        data=args.data,
        model_dir=args.base,
        output_dir=str(output),
        config=config,
        device=args.device,
    )
    lr_history = RecordingCosine.instances[0].history if RecordingCosine.instances else []
    metrics = {
        "epoch_loss": summary.get("epoch_loss") or [],
        "learning_rate": [
            {"step": index + 1, "values": values} for index, values in enumerate(lr_history)
        ],
        "train_items": summary.get("train_items"),
        "calibration_items": summary.get("calibration_items"),
        "eval_items": summary.get("eval_items"),
        "skipped": summary.get("skipped"),
    }
    (output / "laya_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Training complete! Model saved to {summary.get('output_dir', output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
