# AutoLaya

[简体中文](README_ZH.md) | English

**AutoLaya** is a local-first tool for building domain decision models. It turns a domain description and a few real examples into a Laya or GLiNER model that you can train, evaluate, and deploy yourself.

<img width="1920" height="980" alt="img-welcome" src="https://github.com/user-attachments/assets/f63323a5-e757-4aee-a820-2f9b48d2a4f2" />

```text
domain description / seed examples
        → LLM-generated domain text
        → Jev / LLM / human labels
        → human review
        → frozen dataset
        → train Laya / GLiNER
        → evaluate on held-out rows
        → deploy a local decision API
```

<img width="1920" height="980" alt="img-s1" src="https://github.com/user-attachments/assets/4f994a38-d2a6-4035-a828-7f3b90d77a9b" />

Everything happens in one web workspace. You do not need to write training scripts or send business data to a managed training platform.

## What You Can Do

- **Define the domain and Schema:** use Choice, Noul, and Score questions.
- **Prepare data:** add examples manually, import JSONL/CSV, generate with an LLM, or import real held-out data.
- **Label automatically:** use Jev Teacher, direct LLM weak labels, or fully manual labels.
- **Review:** edit, accept, reject, and batch-process samples.
- **Manage datasets:** freeze immutable snapshots and download Canonical, Laya, or GLiNER JSONL.
- **Train models:** Laya Fit + calibration, Laya fine-tuning, and GLiNER2.5 fine-tuning.
- **Evaluate models:** compare Base, Fit, and fine-tuned models, including historical training versions.
- **Test models:** edit Schema and State freely in the Playground and compare models.
- **Deploy models:** start local services and call the Jev-compatible `/v1/systemone`.
- **Export requests:** generate a complete SystemOne cURL request from the Playground.

## Quick Start

Requirements:

- Python 3.12+
- Node.js 20.19+ (22+ recommended)
- 16 GB RAM; 32 GB+ recommended for training
- Optional GPU: NVIDIA CUDA or AMD ROCm; CPU works for Fit and inference

Clone the repository:

```bash
git clone https://github.com/DreamBlooms/Jev-AutoLaya.git
cd Jev-AutoLaya
```

Install and start:

```bash
./deploy.sh setup
./deploy.sh setup-laya
./deploy.sh setup-gliner   # only when using GLiNER
./deploy.sh start
```

### Hand It to Your Agent

You can also give the repository to an agent. Point it to [SKILL.md](SKILL.md) and use a prompt like:

> Read `SKILL.md` first (https://raw.githubusercontent.com/DreamBlooms/Jev-AutoLaya/refs/heads/main/SKILL.md), then help me deploy AutoLaya and build a domain decision model from real examples through Schema, generation, review, dataset creation, training, evaluation, Playground testing, and deployment. Stop and ask before destructive changes or when you need more examples.

The skill contains operating rules, safety checks, the docs map, and the end-to-end workflow.

Open <http://localhost:8000>. API docs are at <http://localhost:8000/docs>.

The first visit opens a guided walkthrough using mock data. It never modifies real projects and can be replayed from Settings → Product guide.

### Configure Keys

`deploy.sh` creates `backend/.env` automatically. Add your LLM and Jev keys there:

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=your_key

# Jev through OpenRouter
JEV_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_JEV_MODEL=~typesafe/jev-latest
```

You can use any OpenAI-compatible Chat Completions service. Without Jev, choose direct LLM labels or no teacher.

Restart after editing:

```bash
./deploy.sh restart
```

### Download Models

Laya and GLiNER base models:

```bash
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
MODEL_SOURCE=hf-mirror MODEL_SET=base ./deploy.sh pull-models
MODEL_SOURCE=ms MODEL_SET=base ./deploy.sh pull-models
```

Laya Fit models:

```bash
FIT_SOURCE=hf ./deploy.sh pull-fit
FIT_SOURCE=hf-mirror ./deploy.sh pull-fit
FIT_SOURCE=hf FIT_BACKBONE_SOURCE=ms ./deploy.sh pull-fit
```

### GPU

NVIDIA CUDA:

```bash
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-laya
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-gliner
```

For AMD ROCm or CPU, use the matching PyTorch wheel index:

```bash
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/rocm6.4 ./deploy.sh setup-laya
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/cpu ./deploy.sh setup-laya
```

## First Use

1. Open AutoLaya and finish the first-visit guide.
2. Create a project and choose its languages.
3. Add Choice, Noul, or Score questions in Schema.
4. Add seeds or import JSONL/CSV from a template.
5. Generate data and review the results.
6. Freeze a dataset.
7. Train Laya or GLiNER.
8. Compare models in Evaluation and test inputs in the Playground.
9. Deploy from Models to get a local `/v1/systemone` URL.

See [Getting Started](docs/guide/en/getting-started.md) for the full walkthrough.

## Documentation

| Document | Contents |
|---|---|
| [User Guide](docs/guide/en/README.md) | Complete usage guide |
| [Getting Started](docs/guide/en/getting-started.md) | Install, configure, start, and build the first project |
| [Project & Data Workflow](docs/guide/en/project-workflow.md) | Schema, seeds, generation, review, datasets |
| [Training & Evaluation](docs/guide/en/training-evaluation.md) | Laya, GLiNER, evaluation, artifacts, Playground |
| [Deployment & API](docs/guide/en/deployment-api.md) | Deploy, call endpoints, backup, security |
| [Troubleshooting](docs/guide/en/troubleshooting.md) | Common problems and fixes |
| [API Reference](docs/API.md) | Complete interface reference for integrations |
| [Design](docs/DESIGN.md) | Architecture and design record |

## Operations

```bash
./deploy.sh start
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh stop
```

Back up at least:

- `backend/.env`
- `data/autolaya.db`
- `data/datasets/`
- `data/artifacts/`
- `models/` if you do not want to download them again

## Known Limitations

- The management API has no built-in login or authentication; do not expose it publicly.
- Multi-label decisions are not supported; use multiple Noul questions instead.
- GLiNER provides labels and confidence, not full calibrated probabilities.
