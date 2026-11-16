---
name: autolaya
description: "Deploy AutoLaya and guide an end-to-end domain decision-model build: define Schema, prepare seeds/data, generate and review samples, freeze datasets, train Laya or GLiNER, evaluate, test in Playground, and deploy a local API. Use when operating, configuring, troubleshooting, or extending AutoLaya for a user."
---

# AutoLaya Operator Skill

Use this skill to operate AutoLaya safely and to guide a user from a domain description to a deployed decision model.

## Core Rule

**Read the existing docs before explaining details or inventing commands.** Do not duplicate long UI instructions, API payloads, or troubleshooting tables in chat. Point to the relevant document and summarize only the decision the user needs.

Docs map:

| Need | Read |
|---|---|
| First install, keys, model download, first project | [docs/guide/getting-started.md](docs/guide/getting-started.md) |
| Schema, seeds/import, generation, review, snapshots | [docs/guide/project-workflow.md](docs/guide/project-workflow.md) |
| Laya/GLiNER training, evaluation, artifacts, Playground | [docs/guide/training-evaluation.md](docs/guide/training-evaluation.md) |
| Serving, `/v1/systemone`, auth, backups | [docs/guide/deployment-api.md](docs/guide/deployment-api.md) |
| User-facing failures and recovery | [docs/guide/troubleshooting.md](docs/guide/troubleshooting.md) |
| Exact REST payloads and endpoints | [docs/API.md](docs/API.md) |
| Current capabilities and limits | [docs/STATUS.md](docs/STATUS.md) |
| Internals only when changing/debugging code | [docs/DESIGN.md](docs/DESIGN.md) |

Chinese docs mirror these paths under `docs/guide/` and `docs/API_ZH.md`.


## Hand This Repository to Your Agent

This repository is designed to be handed to an agent together with this `SKILL.md` file.

Give the agent the repository and a prompt such as:

> Read `SKILL.md` first, then help me deploy AutoLaya and build a domain decision model from real examples through Schema, generation, review, dataset creation, training, evaluation, Playground testing, and deployment. Stop and ask before destructive changes or when you need more examples.

The agent should use this skill for operating rules, the docs map for details, and the user's real use case and samples for the actual project.

## Understand the Real Use Case First

Before creating a project, Schema, or generation job, make sure you understand the user's actual use case:

- What decision is being made, and what action follows from it?
- Who consumes the answer, and what is the cost of a wrong answer?
- What are the labels, score levels, and genuinely ambiguous cases?
- What inputs occur in production: language, length, structure, noise, and frequency?
- What latency, cost, and review capacity are acceptable?
- Which real examples, existing labels, and held-out data already exist?

If the user gives only a vague domain, ask for **5–20 real, anonymized examples** and a clear statement of how each should be judged. Prefer real examples over invented ones.

**Data quality determines final model quality.** Synthetic data and teacher labels are starting points, not ground truth. Use human-confirmed labels, check label consistency and boundary cases, cover hard negatives, and keep real held-out data for final evaluation. Do not optimize for a fast training run at the cost of a dataset that does not represent the real use case.

## Safety Rules

1. Never print, copy, commit, or expose API keys, SSH passwords, `.env` contents, or user data.
2. Ask before destructive actions: deleting a project, snapshot, artifact, or deployment; overwriting `backend/.env`; resetting `data/`.
3. Before restarting AutoLaya, check for active jobs. Queued jobs survive a restart; running jobs may fail and need to be restarted.
4. Do not expose the management UI or API publicly. There is no built-in auth.
5. Do not claim a model, GPU path, or integration works unless it was verified in this environment.
6. Do not commit changes unless the user explicitly asks.

## First Contact

Determine which mode the user needs:

- **Existing deployment:** check health first; do not reinstall.
- **Fresh local install:** follow `deploy.sh` setup.
- **Remote deployment:** use the host, path, and credentials supplied by the user; preserve `.env`, `data/`, `models/`, and virtual environments.
- **Build a model:** ask for the real decision, who uses it, 5–20 real examples if available, existing labels/held-out data, target model, and whether data already exists.

### Baseline Checks

```bash
pwd
./deploy.sh status
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/v1/config
```

If the host or port differs, use the user's actual URL.

For active work:

```bash
curl -s 'http://localhost:8000/api/v1/generation-jobs'
curl -s 'http://localhost:8000/api/v1/training-jobs'
curl -s 'http://localhost:8000/api/v1/evaluations'
```

## Deployment Playbook

Only deploy what is needed. Do not reinstall runtimes when they are already ready.

```bash
./deploy.sh setup
./deploy.sh setup-laya
./deploy.sh setup-gliner          # only when GLiNER is required
./deploy.sh start
```

Model downloads:

```bash
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf ./deploy.sh pull-fit
```

GPU install uses the matching PyTorch wheel index. See the quick-start guide rather than guessing a wheel URL.

After deployment:

```bash
./deploy.sh status
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/v1/config
```

Confirm `llmConfigured`, `jevConfigured`, `availableDevices`, `layaRuntimeReady`, and `glinerRuntimeReady` before starting a model workflow.

### Remote Sync

- Preserve `backend/.env`, `data/`, `models/`, `backend/.venv`, `backend/laya-venv`, and `backend/gliner-venv`.
- Sync application code and built assets, restart, then repeat health/config checks.
- Do not copy local secrets to a remote host unless the user asks.
- Do not run a remote restart while jobs are active without confirmation.

## Full Build Checklist

Use the UI or API. Prefer the API when the user wants repeatable automation.

### 1. Project and Schema

- Create one project for one domain.
- Add at least one `Choice`, `Noul`, or `Score` question.
- Validate keys are unique and options are meaningful.
- Detail: [project workflow](docs/guide/project-workflow.md).

### 2. Seeds and Samples

- Add 5–20 real seeds when possible.
- Use JSONL/CSV templates for bulk input.
- Imported rows remain `pending`.
- Real held-out data must be marked as held out.
- Detail: [seeds and import](docs/guide/project-workflow.md).

### 3. Generate Data

- Choose Jev Teacher, direct LLM labels, or no teacher.
- Set count, languages, difficulty mix, negative ratio, and label balancing.
- Advanced options include custom prompt, Think budget, Think level, and temperature.
- Preview the LLM request before launching a large job.
- Detail: [generation](docs/guide/project-workflow.md).

### 4. Human Review

- Every question needs an answer before acceptance.
- Use batch accept only after spot-checking quality.
- Reject bad samples with a reason.
- Do not skip review for production data.
- Detail: [review](docs/guide/project-workflow.md).

### 5. Freeze Dataset

- Confirm accepted samples are complete.
- Freeze a snapshot and verify split counts and label distribution.
- Require real held-out data for formal evaluation.
- Detail: [freeze a dataset](docs/guide/project-workflow.md).

### 6. Train

- Start with Laya Fit for a baseline.
- Fine-tune Laya when data and hardware justify it.
- GLiNER is fine-tune only.
- Confirm the runtime and device before launching.
- Detail: [training](docs/guide/training-evaluation.md).

### 7. Evaluate

- Evaluate on validation/test rows, not training rows.
- Compare Base, Fit, fine-tuned, and optionally Jev.
- Use “More” to select historical trained versions.
- Prefer held-out results over training loss.
- Detail: [evaluation](docs/guide/training-evaluation.md).

### 8. Test in Playground

- Use Playground for single-input checks without creating datasets or jobs.
- Use project Schema, presets, or a custom editable Schema.
- State may be a string, object, or array.
- Export a SystemOne cURL when the user needs an integration example.
- Detail: [Playground](docs/guide/training-evaluation.md).

### 9. Deploy and Verify

- Deploy the selected artifact.
- Confirm `/health`.
- Call `/v1/systemone` with the same questions used during training.
- For GLiNER, call `/v1/classify` or the compatible mapping.
- Detail: [deployment](docs/guide/deployment-api.md).

## API Quick Reference

Base URL:

```text
http://localhost:8000/api/v1
```

Use [docs/API.md](docs/API.md) for request bodies and response fields. The most common workflow endpoints are:

```text
POST /projects
POST /projects/{id}/questions
POST /projects/{id}/seeds
POST /projects/{id}/samples/import
POST /projects/{id}/generate
GET  /generation-jobs/{id}/events
POST /samples/{id}/accept
POST /projects/{id}/datasets
POST /training-jobs
GET  /training-jobs/{id}/events
POST /evaluations
POST /playground/run
POST /deployments
```

Rules:

- Use the API for repeatable automation.
- Do not poll aggressively; use SSE event endpoints for long jobs.
- Playground and base-model loading can take 10–60 seconds.
- Treat model execution as serialized; do not launch overlapping GPU-heavy runs.

## Decision Guide

### “Deploy this for me”

-> Follow the deployment playbook, verify health/config, stop before creating data unless asked.

### “Build a model from this domain”

-> Get the domain and schema first. Then project → Schema → seeds → generation → review → snapshot → Fit → evaluation → deploy.

### “Test this text/model”

-> Use Playground. Do not create training data just to test one input.

### “Why is training/evaluation bad?”

-> Check data size, label quality, held-out leakage, selected base, and whether the correct snapshot/artifact was used. Read evaluation output before changing parameters.

### “Add/fix a feature”

-> Read [DESIGN.md](docs/DESIGN.md) only for internals. Inspect current routes and tests. Run:

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest
cd frontend && npm run typecheck && npm run build
```

## Completion Criteria

Before telling the user the workflow is complete, verify:

- the real use case and decision boundary are clear;
- project has a valid Schema;
- real examples and held-out data were used where possible;
- generated samples and labels were reviewed and confirmed;
- snapshot exists and contains held-out data;
- training job completed and an artifact exists;
- evaluation used validation/test rows;
- deployment health check passes;
- a real inference request returns answers;
- no secrets or user data were exposed.
