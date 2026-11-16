# AutoLaya User Guide

Welcome to AutoLaya. This guide is for people using the product: install it, prepare data, train a model, evaluate it, and deploy it.

You do not need to write training scripts. Define questions, prepare examples, review data, choose a model, and start training from the web UI.

## Guide Contents

| Document | Contents |
|---|---|
| [Getting Started](./getting-started.md) | Install, configure, start, and build the first project |
| [Project & Data Workflow](./project-workflow.md) | Projects, Schema, seeds, generation, review, datasets |
| [Training & Evaluation](./training-evaluation.md) | Laya, GLiNER, evaluation, artifacts, Playground |
| [Deployment & API](./deployment-api.md) | Start services, call APIs, backup, security |
| [Troubleshooting](./troubleshooting.md) | Common problems and fixes |

中文指南：[中文](../README.md)

## System Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| OS | Ubuntu 20.04+ / macOS 12+ | Linux |
| Python | 3.12+ | 3.12 / 3.13 |
| Node.js | 20.19+ | 22+ |
| Memory | 16 GB | 32 GB+ |
| Storage | 30 GB free | 100 GB+ |
| GPU | Optional | NVIDIA CUDA / AMD ROCm |
| Browser | Current Chrome / Edge / Firefox | Chrome |

Docker, PostgreSQL, and an external database are not required. SQLite is the default, and data is stored under `data/`.

## Full Workflow

```text
Create a project
  → define Schema
  → add seeds or import data
  → generate domain text
  → label and review
  → freeze a dataset
  → train Laya / GLiNER
  → evaluate on held-out rows
  → deploy a local API
```

## Main Features

- **Projects and Schema:** one project is one domain and one set of decision questions.
- **Three question types:** Choice, Noul (yes/no probability), and Score.
- **Data preparation:** manual entry, JSONL/CSV templates, LLM generation, and real held-out data.
- **Automatic labeling:** Jev Teacher, direct LLM weak labels, and manual labels.
- **Review:** accept, reject, edit, and batch-process samples.
- **Dataset versions:** frozen snapshots with Canonical, Laya, and GLiNER JSONL.
- **Training:** Laya Fit, Laya fine-tuning, and GLiNER2.5 fine-tuning.
- **Evaluation:** compare Base, Fit, and fine-tuned models, including historical versions.
- **Playground:** edit Schema/State freely, test Base and trained models, and export SystemOne cURL.
- **Deployment:** local model services with a Jev-compatible API.

## Two Model Families

### Laya

For text decisions. Start with Fit for a quick baseline, then fine-tune when you need better quality. Default and multilingual versions are available.

### GLiNER2.5-Decide

For text classification. Use the default model for English and the multi model for multilingual data. Fine-tuning only; it returns labels and confidence.

## Core Concepts

| Concept | Description |
|---|---|
| Project | One domain and one decision Schema |
| Schema | A set of Choice / Noul / Score questions |
| Seed | A real example used to anchor domain language and labels |
| Sample | One domain text waiting for or going through review |
| Snapshot | A frozen dataset version |
| Artifact | A Fit calibration, Laya checkpoint, or GLiNER checkpoint |
| Deployment | A local service started from an artifact |

## Recommended Reading Order

1. First time: [Getting Started](./getting-started.md)
2. Prepare real data: [Project & Data Workflow](./project-workflow.md)
3. Train and evaluate: [Training & Evaluation](./training-evaluation.md)
4. Integrate with an application: [Deployment & API](./deployment-api.md)
5. Something went wrong: [Troubleshooting](./troubleshooting.md)

## Help

- In-app API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`
- Full API reference: [API Reference](../../API.md)
- Current capabilities and limitations: [Status](../../STATUS.md)
