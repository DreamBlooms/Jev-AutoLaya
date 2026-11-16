# Getting Started

This guide takes you from a clean machine to your first domain decision model.

## 1. Prepare the Environment

Check:

```bash
python3 --version   # 3.12+
node --version      # 20.19+; 22+ recommended
npm --version
```

Ubuntu example:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
# Install Node.js 20+
```

## 2. Install

From the AutoLaya directory:

```bash
./deploy.sh setup
```

`setup` installs dependencies, creates `backend/.env`, builds the frontend, and prepares data directories.

Install the Laya runtime:

```bash
./deploy.sh setup-laya
```

Install GLiNER only if needed:

```bash
./deploy.sh setup-gliner
```

### GPU Installation

NVIDIA CUDA:

```bash
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-laya
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-gliner
```

AMD ROCm or CPU:

```bash
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/rocm6.4 ./deploy.sh setup-laya
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/cpu ./deploy.sh setup-laya
```

Use the PyTorch wheel index that matches your driver.

## 3. Configure Keys

Open `backend/.env`. If it does not exist, run `./deploy.sh setup` first.

### 3.1 LLM

Generation requires an OpenAI-compatible Chat Completions service. DeepSeek is the default:

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=your_key
```

OpenRouter, OpenAI, vLLM, Ollama, and other compatible services also work.

### 3.2 Jev Teacher (Optional)

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

Without Jev, choose direct LLM labels or no teacher in the generation page.

### 3.3 GLiNER (Optional)

```env
GLINER_ENABLED=true
GLINER_BASE_MODEL=fastino/GLiNER2.5-Decide
GLINER_MULTI_MODEL=fastino/GLiNER2.5-multi-Decide
```

### 3.4 Restart

```bash
./deploy.sh restart
```

Keys are read only by the backend and are never sent to the browser.

## 4. Download Models

Base models:

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

The local paths are written back to `backend/.env`.

## 5. Start

```bash
./deploy.sh start
```

Open:

- Web UI: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health>

Common commands:

```bash
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh stop
```

### Check Configuration

```bash
curl -s http://localhost:8000/api/v1/config
```

Check:

- `llmConfigured`
- `jevConfigured`
- `availableDevices`
- `layaRuntimeReady`
- `glinerRuntimeReady`

The Settings page also shows these values.

## 6. First Use

The first visit opens a full walkthrough using mock data. It never modifies real projects. Skip it or replay it from Settings → Product guide.

### 6.1 Create a Project

1. Click “New project”.
2. Enter a name and domain description.
3. Choose English, Chinese, or both.

Example:

```text
Name: Support Triage
Domain: SaaS support tickets; decide the team and urgency
```

### 6.2 Define the Schema

In the Schema tab, add questions:

- **Choice:** one of several options, e.g. `team = billing / technical / sales`
- **Noul:** yes/no probability, e.g. “Does this need attention today?”
- **Score:** ordered levels, e.g. “can wait / this week / today”

Use lowercase English keys such as `team`, `urgent`, and `priority`.

### 6.3 Add Data

You can:

- add seeds manually;
- download a JSONL/CSV template and import seeds or samples;
- generate new domain text with an LLM.

Use real business text for seeds when possible, and cover the main labels and edge cases.

### 6.4 Generate and Label

In the Generate page set:

- sample count;
- languages;
- teacher;
- easy / medium / hard mix;
- hard/ambiguous ratio;
- label balancing.

Advanced settings can:

- append a custom prompt;
- set Think budget;
- set Think level;
- set temperature;
- preview the full LLM request body.

Generated samples still require human review.

### 6.5 Review

In the review queue:

1. inspect the sample and teacher answers;
2. edit Choice, Noul, and Score;
3. save answers;
4. accept after every question has an answer;
5. reject unwanted samples.

You can select multiple samples and process them in a batch.

### 6.6 Freeze a Dataset

Open the Datasets tab and click “Freeze snapshot”.

A snapshot includes only accepted samples with answers for every question. You can download:

- Canonical JSONL
- Laya JSONL
- GLiNER JSONL

### 6.7 Train

In the Training tab:

1. select a snapshot;
2. choose the target model and base;
3. choose Fit or fine-tune;
4. choose a device;
5. set parameters;
6. start training.

Start with Laya Fit to get a baseline before fine-tuning.

### 6.8 Evaluate

In Evaluation, select a snapshot and models. Results are grouped into:

- remote baseline
- base models
- trained models

For trained models, click “More” to choose a historical version.

### 6.9 Playground

The Playground tests a single input without creating a job:

- choose a Base or trained model;
- use the project Schema, a preset, or a fully custom Schema;
- enter any valid JSON state;
- inspect answers and probabilities;
- export a SystemOne cURL.

### 6.10 Deploy

On the Models page, choose an artifact and deploy it. You get a local address such as:

```text
http://127.0.0.1:8100/v1/systemone
```

See [Deployment & API](./deployment-api.md) for request examples.

## 7. Data and Backup

Default data location:

```text
data/
├── autolaya.db
├── datasets/
└── artifacts/
```

Back up:

- `backend/.env`
- `data/autolaya.db`
- `data/datasets/`
- `data/artifacts/`
- `models/` if you do not want to download again

## Next Steps

- [Project & Data Workflow](./project-workflow.md)
- [Training & Evaluation](./training-evaluation.md)
- [Deployment & API](./deployment-api.md)
