# Troubleshooting

Start with:

```bash
./deploy.sh status
./deploy.sh logs
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/v1/config
```

## 1. Service Does Not Start

Symptom:

```text
AutoLaya did not become healthy
```

Check:

```bash
tail -n 100 deploy.log
./deploy.sh status
ss -ltnp | grep 8000
```

| Cause | Fix |
|---|---|
| Port 8000 in use | Stop the process or use `BACKEND_PORT=8001 ./deploy.sh start` |
| Dependencies missing | Run `./deploy.sh setup` |
| Frontend not built | `./deploy.sh build` |
| Data directory not writable | Fix `data/` permissions |
| Python too old | Install Python 3.12+ |

## 2. Blank Page or 404 on Refresh

```bash
./deploy.sh build
./deploy.sh restart
```

Do not open `frontend/index.html` directly. Use `http://localhost:8000`.

## 3. LLM Not Configured

Symptoms:

- Generate button disabled;
- missing `LLM_API_KEY` warning;
- `llmConfigured: false`.

Check:

```bash
grep -n 'LLM_' backend/.env
```

Set:

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=your_key
```

Restart:

```bash
./deploy.sh restart
```

## 4. LLM Call Fails

| Error | Fix |
|---|---|
| 401 / 403 | Wrong key or no permission |
| 404 | Wrong base URL or model |
| 429 | Rate limited; reduce concurrency or wait |
| Timeout | Increase timeout or use a faster model |
| Non-JSON output | Use a model with JSON output support |
| Insufficient balance | Top up or switch provider |

Lower concurrency:

```env
LLM_MAX_CONCURRENCY=1
GENERATION_BATCH_SIZE=5
```

## 5. Jev Missing or Labeling Fails

OpenRouter:

```env
JEV_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_JEV_MODEL=~typesafe/jev-latest
```

TypeSafe:

```env
JEV_PROVIDER=typesafe
TYPESAFE_API_KEY=your_key
TYPESAFE_JEV_MODEL=jev-1.14.0
```

Restart. Without Jev, use direct LLM labels or manual labels.

## 6. Generation Pauses, Stalls, or Is Interrupted

- generation jobs can pause and resume;
- queued jobs continue after a restart;
- running jobs may need to be restarted;
- generated samples are not lost.

If no samples are produced:

- check for empty model output;
- check whether all candidates were duplicates;
- check whether the teacher keeps failing;
- read `deploy.log`.

## 7. No Pending Samples

Check:

- the generation job completed;
- sample status is `pending`;
- the review page is not filtered to another project;
- samples were not already batch-processed.

## 8. Cannot Accept a Sample

Every question needs an answer first.

If the teacher returned only some questions, or a new question was added later, complete the answers before accepting.

## 9. Dataset Freeze Fails

### `No accepted samples are available`

Review and accept samples first.

### `Accepted samples are missing accepted answers`

Complete the missing answers and accept again.

### `Add at least one question before freezing a dataset`

Add at least one Schema question.

### No test / validation

Very small datasets cannot guarantee all splits. Add more samples or real held-out rows.

## 10. Laya Runtime Missing

```bash
./deploy.sh setup-laya
```

Check:

```bash
ls backend/laya-venv/bin/python
ls backend/laya-venv/bin/laya-train
ls backend/laya-venv/bin/laya-serve
```

For GPU:

```bash
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-laya
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/rocm6.4 ./deploy.sh setup-laya
```

## 11. Laya Fit Fails

Check:

```bash
grep -n 'LAYA_FIT_' backend/.env
ls -la /path/to/vega-U
ls -la /path/to/Qwen3.5-0.8B
```

Download:

```bash
FIT_SOURCE=hf ./deploy.sh pull-fit
```

Fit does not use epochs. Do not try to fix Fit by changing epochs.

## 12. Laya Fine-Tuning Fails

| Cause | Fix |
|---|---|
| `laya-train` missing | Reinstall the Laya runtime |
| Base model download failed | Use `pull-models` or local paths |
| Out of memory | Lower micro batch and raise accumulation |
| Training interrupted | Restart the job |
| Disk full | Clean old artifacts |

Low memory:

```text
microBatch=2
gradAccum=32
freezeEncoder=true
```

## 13. GLiNER Disabled or Fails

```bash
./deploy.sh setup-gliner
```

```env
GLINER_ENABLED=true
```

Restart and confirm Settings shows GLiNER ready.

GLiNER supports fine-tuning only. If the snapshot lacks a GLiNER export, freeze it again.

## 14. Evaluation Fails

- `Laya Fit` requires a Fit calibration artifact;
- `Laya fine-tuned` requires a Laya checkpoint;
- `GLiNER fine-tuned` requires a GLiNER checkpoint.

Complete the training first.

If only some rows are evaluated, check `EVAL_MAX_ROWS`.

GLiNER does not compute Brier; this is expected.

## 15. Playground Fails

- trained models require a project;
- base models can run without a project;
- Choice questions need at least one option;
- Score questions need labels;
- State must be a string, object, or array;
- the first model load can take 10–60 seconds.

SystemOne image `assets` are not supported, so Playground does not expose them.

## 16. Deployment Fails

### Port in use

Stop the old deployment or choose another port.

```bash
ss -ltnp | grep 810
```

### Status `failed`

Check:

```text
data/artifacts/deployments/<deployment-id>/serve.log
```

Common causes:

- model path missing;
- runtime missing;
- out of memory;
- port conflict.

## 17. CUDA / ROCm Not Detected

```bash
nvidia-smi
rocm-smi
curl -s http://localhost:8000/api/v1/config
```

If only `cpu` is available:

- driver missing;
- CPU-only PyTorch installed;
- GPU not passed through the VM/container.

Reinstall the runtime with the matching wheel index.

## 18. Model Download Fails

Use a mirror:

```bash
MODEL_SOURCE=hf-mirror MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf-mirror ./deploy.sh pull-fit
```

Use ModelScope:

```bash
MODEL_SOURCE=ms MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf FIT_BACKBONE_SOURCE=ms ./deploy.sh pull-fit
```

`vega-U` does not support ModelScope. The Qwen reader does.

## 19. Data Loss or Corruption

Stop and back up:

```bash
./deploy.sh stop
cp data/autolaya.db data/autolaya.db.bak
```

Do not delete the database or `data/` unless you are sure you no longer need the projects and datasets.

## 20. Before Reporting an Issue

Include:

- OS, Python, and Node versions;
- `./deploy.sh status`;
- relevant configuration with keys removed;
- `deploy.log` or model service log;
- reproduction steps;
- job ID and error message.

Never send API keys, real business data, or the full database.
