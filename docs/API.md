# AutoLaya API Reference

> For installation, UI workflows, and serving examples, start with the [User Guide](guide/en/README.md).

Base URL: `http://localhost:8000/api/v1`

All request/response fields use camelCase in the browser API. Database identifiers are UUID strings.

> **Authentication:** the management API has no built-in authentication. Do not expose it publicly. See [Deployment & API](guide/en/deployment-api.md#6-authentication).

---

## Runtime configuration

### `GET /config`

Returns the current runtime configuration.

```json
{
  "data": {
    "device": "cpu",
    "availableDevices": ["cpu", "cuda"],
    "llmConfigured": true,
    "llmProvider": "openai-compatible",
    "llmBaseUrl": "https://api.deepseek.com",
    "llmModel": "deepseek-flash",
    "jevConfigured": true,
    "jevProvider": "openrouter",
    "jevModel": "~typesafe/jev-latest",
    "targets": ["laya", "gliner"],
    "reservedTargets": [],
    "layaModels": {
      "default": "convaiinnovations/laya-typed-decisions",
      "multilingual": "convaiinnovations/laya-multilingual"
    },
    "glinerModels": {
      "english": "fastino/GLiNER2.5-Decide",
      "multilingual": "fastino/GLiNER2.5-multi-Decide"
    }
  }
}
```

### `POST /config/device`

```json
{ "device": "auto" }
```

Supported: `auto`, `cpu`, `cuda`, `mps`, `rocm`.

---

## Projects

| Method | Path | Description |
|---|---|---|
| POST | `/projects` | Create a domain project |
| GET | `/projects` | List projects |
| GET | `/projects/{id}` | Project detail |
| PUT | `/projects/{id}` | Update project |
| POST | `/projects/{id}/delete` | Delete project |

### Create project

```json
{
  "name": "Support triage",
  "domain": "Customer support tickets",
  "languages": ["zh", "en"]
}
```

---

## Question Schemas

| Method | Path | Description |
|---|---|---|
| POST | `/projects/{id}/questions` | Add Choice/Noul/Score |
| GET | `/projects/{id}/questions` | List questions |
| PUT | `/projects/{id}/questions/{qid}` | Update question |
| DELETE | `/projects/{id}/questions/{qid}` | Delete question |

### Choice question

```json
{
  "key": "team",
  "type": "choice",
  "instructions": "Which team should handle this ticket?",
  "criteria": {
    "billing": "Refunds, invoices, payments",
    "technical": "Bugs, outages, API issues",
    "sales": "Pricing, trials, quotes"
  }
}
```

### Noul question

```json
{
  "key": "urgent",
  "type": "noul",
  "instructions": "Does this need attention today?"
}
```

### Score question

```json
{
  "key": "urgency",
  "type": "score",
  "instructions": "How urgent is this ticket?",
  "criteria": ["can wait", "this week", "today"]
}
```

---

## Seeds and prompts

| Method | Path | Description |
|---|---|---|
| POST | `/projects/{id}/seeds` | Import seed samples |
| POST | `/projects/{id}/heldout` | Import real held-out samples (forced test split) |
| GET | `/projects/{id}/seeds` | List seeds |
| GET | `/projects/{id}/seeds/template?format=jsonl` | Download JSONL seed template |
| GET | `/projects/{id}/seeds/template?format=csv` | Download CSV seed template |
| POST | `/projects/{id}/seeds/import` | Upload JSONL/CSV (`multipart/form-data`, field `file`) |
| DELETE | `/seeds/{id}` | Delete seed |
| POST | `/projects/{id}/schema-suggestions` | LLM Schema suggestion |
| POST | `/projects/{id}/generation-prompts` | Save prompt template |

---

## Generation

### `POST /projects/{id}/generate`

```json
{
  "count": 500,
  "languages": ["zh", "en"],
  "difficulty": { "easy": 0.5, "medium": 0.35, "hard": 0.15 },
  "negativeRatio": 0.1,
  "labelBalanced": true,
  "teacher": "jev",
  "customPrompt": "Prefer short, realistic support tickets.",
  "systemPromptTemplate": "System for {{project_name}} in {{language}}.",
  "userPromptTemplate": "Use {{schema_json}} and {{seeds_json}} to generate {{count}} items.",
  "llm": {
    "baseUrl": "https://api.deepseek.com",
    "model": "deepseek-flash",
    "temperature": 0.7,
    "thinkBudget": 512,
    "thinkLevel": "medium"
  }
}
```

`teacher` can be `jev`, `llm`, `none`, or `human`. With `llm`, the same generation call also asks the LLM for weak labels, writes them as `teacher=llm`, and still routes every sample through human review. `customPrompt` is appended to the generation instructions without changing the JSON output shape. `thinkBudget` is sent as `reasoning.max_tokens`, and `thinkLevel` as `reasoning_effort`, for providers that support them. The preview endpoint returns the effective model, endpoint, language, batch size, and full Chat Completions body.

Available prompt placeholders: `project_name`, `project_domain`, `language`, `count`, `difficulty`, `negative_ratio`, `schema_json`, `seeds_json`, `sample_shape`, `label_rule`, `label_instruction`, `balancing`, `negative_instruction`, `default_system`, `default_user`, and `custom_prompt`. A custom template replaces the default content; use `default_system` / `default_user` to reuse it.

Response: `202` with a `GenerationJob`.

| Method | Path | Description |
|---|---|---|
| GET | `/generation-jobs/{id}` | Job status |
| GET | `/generation-jobs/{id}/events` | SSE progress |
| POST | `/generation-jobs/{id}/pause` | Pause |
| POST | `/generation-jobs/{id}/resume` | Resume |
| POST | `/generation-jobs/{id}/cancel` | Cancel |

Progress events:

```text
data: {"stage":"generating","completed":120,"total":500}
data: {"stage":"labeling","completed":80,"total":500}
data: {"stage":"filtering","completed":500,"total":500}
data: {"stage":"completed","accepted":421,"rejected":79}
```

---

## Samples and annotations

| Method | Path | Description |
|---|---|---|
| GET | `/samples?status=pending&projectId=` | Review queue |
| GET | `/samples/{id}` | Sample + annotations |
| POST | `/samples/{id}/accept` | Accept annotations |
| POST | `/samples/{id}/reject` | Reject sample |
| PUT | `/samples/{id}/annotations/{qid}` | Edit answer |
| POST | `/samples/{id}/reannotate` | Re-run teacher |
| GET | `/projects/{id}/samples/template?format=jsonl` | Download JSONL template |
| GET | `/projects/{id}/samples/template?format=csv` | Download CSV template |
| POST | `/projects/{id}/samples/import` | Upload JSONL/CSV (`multipart/form-data`, field `file`) |

Bulk import columns:

```text
state,labels,language,difficulty,heldout
```

`state` is a JSON object (or a plain string, stored as `{"text": "..."}`). `labels` is a JSON object keyed by question key. `heldout` accepts `true/false/1/0/yes/no`. The response reports `imported`, `heldout`, and the created samples.

### Annotation shape

```json
{
  "questionId": "team",
  "answer": {
    "type": "choice",
    "choice": "billing",
    "confidence": 0.93,
    "probabilities": {
      "billing": 0.93,
      "technical": 0.05,
      "sales": 0.02
    }
  },
  "status": "accepted",
  "reviewer": "human"
}
```

---

## Datasets

| Method | Path | Description |
|---|---|---|
| POST | `/projects/{id}/datasets` | Freeze a dataset snapshot |
| GET | `/datasets/{id}` | Snapshot stats |
| DELETE | `/datasets/{id}` | Delete snapshot record and export files |
| GET | `/datasets/{id}/download?format=canonical` | Download Canonical JSONL |
| GET | `/datasets/{id}/download?format=laya` | Download Laya JSONL |
| GET | `/datasets/{id}/download?format=gliner` | GLiNER JSONL |

Snapshot response includes split counts and label distribution. Deleting a snapshot is blocked while a training or evaluation job is pending/running. Related training/evaluation records are removed; model artifacts are kept. New snapshots use `max(existing version) + 1`.

---

## Training

### `POST /training-jobs`

```json
{
  "projectId": "uuid",
  "snapshotId": "uuid",
  "target": "laya",
  "mode": "fit",
  "device": "auto",
  "config": {
    "baseModel": "convaiinnovations/laya-typed-decisions",
    "epochs": 4,
    "microBatch": 4,
    "gradAccum": 8,
    "loss": "rlcd"
  }
}
```

`target`: `laya` or `gliner`.

`mode`: `fit` or `finetune`.

| Method | Path | Description |
|---|---|---|
| GET | `/training-jobs` | List jobs |
| GET | `/training-jobs/{id}` | Job detail |
| GET | `/training-jobs/{id}/events` | SSE progress |
| POST | `/training-jobs/{id}/cancel` | Cancel |

---

## Evaluation

### `POST /evaluations`

```json
{
  "snapshotId": "uuid",
  "models": ["jev", "laya-base", "laya-fit", "laya-finetuned"],
  "device": "auto",
  "artifactIds": {
    "laya-fit": "artifact-uuid",
    "laya-finetuned": "artifact-uuid"
  }
}
```

`artifactIds` is optional. It selects a specific historical artifact for `laya-fit`, `laya-finetuned`, or `gliner-finetuned`; omitted keys use the latest artifact of that kind.

| Method | Path | Description |
|---|---|---|
| GET | `/evaluations/{id}` | Results |
| GET | `/evaluations/{id}/report` | Download JSON/Markdown |

`results.modelInfo` records each evaluated model’s role (`remote`, `base`, `fit`, `finetuned`), target, source, and exact artifact metadata (name, path, kind, creation time) so historical runs remain traceable.

---

## Playground

### `POST /playground/run`

Run a single input against a base model or a trained artifact without persisting data.

```json
{
  "projectId": "uuid",
  "model": "laya-finetuned",
  "artifactId": "artifact-uuid",
  "state": {"ticket": "I was charged twice this month."},
  "questions": [
    {
      "key": "team",
      "type": "choice",
      "instructions": "Which team should handle this?",
      "criteria": {"billing": "Refunds and payments", "technical": "Bugs and outages"}
    },
    {
      "key": "urgent",
      "type": "noul",
      "instructions": "Does this need attention today?",
      "criteria": {"true": "Needs attention today", "false": "Can wait"}
    },
    {
      "key": "priority",
      "type": "score",
      "instructions": "What is the priority?",
      "criteria": ["can wait", "this week", "today"]
    }
  ],
  "device": "auto"
}
```

`projectId` is optional when `questions` are supplied; trained artifacts still require a project. `state` accepts a string, object, or array. `questions` should be omitted to use the project’s current Schema, or supplied to test a fully custom Schema.

`model` supports `laya-base`, `laya-multi-base`, `laya-fit`, `laya-finetuned`, `gliner-base`, `gliner-multi-base`, and `gliner-finetuned`. `artifactId` is optional for trained models; omitted means the latest artifact of that kind. The response contains `modelInfo`, `answers`, `latencyMs`, `routing`, and `usage`.

SystemOne `assets` are image-only and are not supported by the local text runtimes, so the Playground does not expose them in the request editor or exported cURL.

---


## Model artifacts

| Method | Path | Description |
|---|---|---|
| GET | `/artifacts` | List fit / fine-tune artifacts |
| GET | `/artifacts/{id}` | Artifact metadata and metrics |
| GET | `/artifacts/{id}/download` | Download artifact directory as a ZIP |
| DELETE | `/artifacts/{id}` | Delete artifact (must not be active) |

## Deployment

```json
{
  "artifactId": "uuid",
  "target": "laya",
  "host": "127.0.0.1",
  "port": 8100
}
```

| Method | Path | Description |
|---|---|---|
| POST | `/deployments` | Start a model service |
| GET | `/deployments` | List instances |
| GET | `/deployments/{id}` | Status/health |
| POST | `/deployments/{id}/stop` | Stop |
| POST | `/deployments/{id}/restart` | Restart |
| DELETE | `/deployments/{id}` | Stop and delete deployment |

Both fit calibration artifacts and fine-tuned checkpoints can be deployed. Laya exposes a Jev-compatible API:

```text
POST /v1/systemone
POST /v1/systemone/batch
GET  /health
```

GLiNER deployment exposes `/v1/classify` and a Jev-compatible `/v1/systemone` mapping.

## Job events and cancellation

```text
GET  /generation-jobs/{id}/events
GET  /training-jobs/{id}/events
GET  /evaluations/{id}/events
POST /generation-jobs/{id}/cancel
POST /training-jobs/{id}/cancel
POST /evaluations/{id}/cancel
```

Events use `text/event-stream` and the same camelCase fields as the job response.

---

## Error format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "..."
  }
}
```

Common codes:

- `VALIDATION_ERROR`
- `NOT_FOUND`
- `PROVIDER_ERROR`
- `LLM_ERROR`
- `TEACHER_ERROR`
- `TRAINING_ERROR`
- `DEPLOYMENT_ERROR`
- `RESERVED_TARGET`
- `SNAPSHOT_IN_USE`
