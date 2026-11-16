from __future__ import annotations

import argparse
import os
from pathlib import Path

BASE_MODELS = {
    "laya-typed-decisions": ("convaiinnovations/laya-typed-decisions", "LAYA_BASE_MODEL"),
    "laya-multilingual": ("convaiinnovations/laya-multilingual", "LAYA_MULTI_MODEL"),
    "GLiNER2.5-Decide": ("fastino/GLiNER2.5-Decide", "GLINER_BASE_MODEL"),
    "GLiNER2.5-multi-Decide": ("fastino/GLiNER2.5-multi-Decide", "GLINER_MULTI_MODEL"),
}
FIT_MODELS = {
    "vega-U": ("nandakishorm/vega-U", "LAYA_FIT_MODEL"),
    "Qwen3.5-0.8B": ("Qwen/Qwen3.5-0.8B", "LAYA_FIT_BACKBONE"),
}


def update_env(path: Path, values: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    seen: set[str] = set()
    output = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else None
        if key in values:
            output.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in seen:
            output.append(f"{key}={value}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8")
    path.chmod(0o600)


def pull_hf(repo: str, destination: Path, mirror: bool) -> None:
    if mirror:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    from huggingface_hub import snapshot_download

    snapshot_download(repo, local_dir=str(destination), max_workers=4)


def pull_ms(repo: str, destination: Path) -> None:
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise SystemExit("modelscope is not installed. Run: pip install modelscope") from exc
    snapshot_download(repo, local_dir=str(destination))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download AutoLaya base or fit models")
    parser.add_argument("--source", choices=["hf", "hf-mirror", "ms"], default="hf")
    parser.add_argument(
        "--backbone-source",
        choices=["hf", "hf-mirror", "ms"],
        default="",
        help="Source for the Qwen fit backbone; defaults to --source",
    )
    parser.add_argument("--set", choices=["base", "fit", "all"], default="base")
    parser.add_argument("--root", default="models")
    parser.add_argument("--env-file", default="")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.set == "fit" and args.source == "ms":
        raise SystemExit(
            "vega-U supports hf and hf-mirror only; use FIT_BACKBONE_SOURCE=ms for Qwen"
        )
    if args.set == "fit":
        backbone_source = args.backbone_source or args.source
        selected = [
            ("vega-U", FIT_MODELS["vega-U"], args.source),
            ("Qwen3.5-0.8B", FIT_MODELS["Qwen3.5-0.8B"], backbone_source),
        ]
    else:
        selected = [(directory, spec, args.source) for directory, spec in BASE_MODELS.items()]
    env_values: dict[str, str] = {}
    for directory, (repo, env_key), source in selected:
        destination = root / directory
        print(f"Pulling {repo} -> {destination} from {source}", flush=True)
        if source == "ms":
            pull_ms(repo, destination)
        else:
            pull_hf(repo, destination, mirror=source == "hf-mirror")
        env_values[env_key] = str(destination)
    if args.env_file:
        update_env(Path(args.env_file), env_values)
        print(f"Updated {args.env_file}", flush=True)
    for key, value in env_values.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
