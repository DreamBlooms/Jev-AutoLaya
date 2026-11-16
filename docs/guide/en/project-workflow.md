# Project & Data Workflow

This guide covers Schema design, seeds, generation, review, and dataset snapshots.

## 1. What a Project Contains

```text
Project
  ├── Schema: question definitions
  ├── Seeds: real examples
  ├── Samples: data waiting for or going through review
  ├── Dataset snapshots: frozen training data
  └── Model artifacts: training results
```

Use one project for one domain. Do not mix unrelated businesses.

## 2. Create a Project

Click “New project”:

| Field | Description | Example |
|---|---|---|
| Name | Display name | Support Triage |
| Domain | Business, input, and decisions | SaaS tickets; decide team and urgency |
| Languages | Generation and evaluation languages | English, Chinese |

## 3. Design the Schema

Open the project’s Schema tab and add at least one question.

### 3.1 Choice

```json
{
  "key": "team",
  "type": "choice",
  "instructions": "Which team should handle this ticket?",
  "criteria": {
    "billing": "Refunds, invoices, duplicate charges, payments",
    "technical": "Bugs, outages, API errors, performance",
    "sales": "Pricing, trials, quotes, contracts"
  }
}
```

Each option has a key and a description.

### 3.2 Noul

```json
{
  "key": "urgent",
  "type": "noul",
  "instructions": "Does this need attention today?"
}
```

Answers are probabilities from 0 to 1. Values at or above 0.5 export as yes.

### 3.3 Score

```json
{
  "key": "priority",
  "type": "score",
  "instructions": "What is the priority?",
  "criteria": ["can wait", "this week", "today"]
}
```

Labels are ordered from low to high. Exported scores start at 0.

### 3.4 Guidelines

- Use lowercase English keys.
- Keep options mutually exclusive; use multiple Noul questions for multi-label needs.
- Avoid an unbounded “other” option.
- Instructions describe what to decide; descriptions define boundaries.
- Keep questions in one project focused on the same scenario.

## 4. Seeds and Import

### 4.1 Add Seeds Manually

Open the Seeds tab and click “Add seed”.

State JSON:

```json
{
  "ticket": "I was charged twice this month, please refund the duplicate."
}
```

Optional labels:

```json
{
  "team": "billing"
}
```

Click “Send to review” to turn seeds into pending samples.

### 4.2 Download Templates

Both Seeds and Samples provide:

- JSONL template
- CSV template

Seed columns:

```text
state,labels,language
```

Samples also support `difficulty` and `heldout`.

### 4.3 Bulk Import

Rules:

- 20 MB and 5000 rows per file;
- UTF-8;
- `state` may be a JSON object or a plain string;
- label keys must already exist in the Schema;
- imported data remains pending and requires review.

### 4.4 Real Held-Out Data

Use real business data for testing when possible.

Enable “Real held-out sample” when creating a manual sample. These rows always enter the test split and never train the model.

Recommended:

- 50–200 rows for formal evaluation;
- at least 20 for a small project;
- cover all labels and main edge cases;
- do not reuse the same held-out set to tune repeatedly.

## 5. Generate Data

Open the Generate tab.

| Field | Description |
|---|---|
| Samples | Up to 2000 per job |
| Languages | Chinese / English |
| Teacher | Jev, direct LLM labels, or no teacher |
| Easy / Medium / Hard | Percentages totaling 100% |
| Hard/ambiguous ratio | Prompt hint from 0 to 1 |
| Balance labels | Ask for even label coverage |

### 5.1 Teacher Options

**Jev Teacher**

- uses Jev for teacher answers;
- requires a Jev key;
- still requires human review.

**Direct LLM labels**

- the generator also emits weak labels;
- cheaper, but quality depends on the model;
- must be reviewed.

**No teacher**

- generates text only;
- humans fill every answer.

### 5.2 Advanced Settings

Expand Advanced settings to:

- append a custom prompt;
- fully customize the System Prompt and User Prompt templates;
- set Think budget (`reasoning.max_tokens`);
- set Think level (`reasoning_effort`);
- set temperature;
- preview the full LLM request body.

The “Custom Prompt templates” switch is off by default and uses the built-in templates. Turning it on shows the default System and User templates as a starting point. A custom template replaces the default and may use `{{x}}` placeholders for the current project, Schema, seeds, difficulty, and sampling values. Common placeholders include `{{project_name}}`, `{{language}}`, `{{count}}`, `{{schema_json}}`, `{{seeds_json}}`, `{{default_system}}`, `{{default_user}}`, and `{{custom_prompt}}`. The full list is shown in Advanced settings.

Think budget and level only take effect on providers that support those parameters. Leave blank to use defaults.

### 5.3 Generation Lifecycle

The job shows:

- progress;
- generated, accepted, and rejected counts;
- current stage;
- errors.

Jobs can be paused, resumed, or cancelled. Generated samples still need review.

### 5.4 Quality Tips

- Start with 50–200 samples.
- Use 5–20 real seeds.
- Inspect short, long, negative, and ambiguous inputs.
- Do not rely only on synthetic data for final evaluation.

## 6. Review

Open “Review queue”.

### 6.1 Queue

- pending samples appear on the left;
- filter by project;
- select multiple samples for batch accept/reject;
- only pending samples are shown.

### 6.2 Edit Answers

Each question has a card:

- Choice: select an option;
- Noul: enter a probability from 0 to 1;
- Score: select a label or enter a score;
- optionally add a review note;
- click “Save answer”.

### 6.3 Accept and Reject

Every question needs an answer before accepting.

- Accept: included in the next snapshot;
- Reject: excluded from training;
- Re-run Jev: fetch teacher answers again.

## 7. Freeze a Dataset

Open Datasets and click “Freeze snapshot”.

### 7.1 Inclusion Rules

- sample is accepted;
- every question has an answer;
- the data can be exported.

If an accepted sample is missing answers, freezing fails. Complete it in review and accept again.

### 7.2 Versions

Each freeze creates a new version. Old snapshots remain usable and do not affect existing training jobs.

### 7.3 Splits

- samples from the same source are not split across train and test;
- real held-out rows always enter test;
- the system tries to provide train / validation / test;
- very small datasets may not support all three.

### 7.4 Download Formats

Each snapshot provides:

- **Canonical JSONL:** complete fields for audit and conversion;
- **Laya JSONL:** for Laya training;
- **GLiNER JSONL:** for GLiNER fine-tuning.

### 7.5 Delete a Snapshot

Each snapshot card has Delete:

- removes the record and export files;
- blocked while training or evaluation is active;
- keeps model artifacts.

Deletion is irreversible. Download the JSONL or back up `data/datasets/` first.

## 8. Data Quality Checklist

- [ ] Every label has enough samples.
- [ ] Long-tail labels are not ignored.
- [ ] Hard, negative, ambiguous, and long inputs were sampled.
- [ ] No obvious duplicates.
- [ ] Teacher/human conflicts were rechecked.
- [ ] Real held-out rows are marked.
- [ ] No source leakage across train and test.
- [ ] Label distribution matches the business.

## 9. Backup

Back up:

- `backend/.env`
- `data/autolaya.db`
- `data/datasets/`
- `data/artifacts/`
- `models/`

## Next Steps

- [Training & Evaluation](./training-evaluation.md)
- [Deployment & API](./deployment-api.md)
