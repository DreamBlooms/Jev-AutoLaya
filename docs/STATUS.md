# AutoLaya Status

> Updated: 2026-11-16

## Available

- Projects, Choice / Noul / Score Schema, seeds, sample import, and review queue.
- LLM data generation with custom prompt, Think budget, Think level, temperature, and request preview.
- Jev Teacher, direct LLM labels, and manual labeling.
- Immutable dataset snapshots with Canonical, Laya, and GLiNER JSONL download and deletion.
- Laya Fit + calibration, Laya fine-tuning, and GLiNER2.5 fine-tuning.
- Held-out evaluation for Base, Fit, fine-tuned models, and historical versions.
- Model artifact ZIP download and local deployment.
- Playground for custom Schema/State, Base and trained model testing, and SystemOne cURL export.
- First-visit guide, light/dark themes, and English/Chinese UI.
- Local `deploy.sh` deployment; Docker is not required.

## Verified

- DeepSeek generated English and Chinese data.
- Jev labeled real samples through OpenRouter.
- Laya Fit, Laya fine-tuning, and GLiNER English/multilingual training, evaluation, and deployment completed.
- Local services expose `/v1/systemone` and `/v1/classify`.
- Playground tested Base and a selected historical checkpoint.

## Known Limitations

- The management UI has no built-in authentication; do not expose it publicly.
- Multi-label decisions are not supported; use multiple Noul questions.
- GLiNER exposes confidence, not full calibrated probabilities.
- SystemOne image assets are not supported.

## Recommended Use

- Local or private-network deployment.
- Human review as the final quality gate.
- Real held-out data for final evaluation.
- Start with Laya Fit, then decide whether fine-tuning is needed.
