# Training & Evaluation

This guide explains how to train a dataset into a Laya or GLiNER model and compare results on held-out data.

## 1. Choose a Training Path

| Path | Target | Speed | Use Case |
|---|---|---|---|
| Laya Fit + calibration | Laya | Fast | Quick baseline |
| Laya fine-tune | Laya | Slow | More data, better quality |
| GLiNER fine-tune | GLiNER2.5 | Medium | Text classification, English or multilingual |

Recommended order:

```text
Laya Fit
  → evaluate
  → Laya fine-tune
  → compare on the same held-out set
  → deploy the model that meets requirements
```

## 2. Before Training

Confirm:

- a frozen dataset snapshot exists;
- accepted samples are complete;
- real held-out data exists;
- no source leakage across train and test;
- the target runtime is installed.

Laya:

```bash
./deploy.sh setup-laya
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf ./deploy.sh pull-fit
```

GLiNER:

```bash
./deploy.sh setup-gliner
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
```

Set:

```env
GLINER_ENABLED=true
```

The Settings page shows whether each runtime is ready.

## 3. Devices

- `auto`: choose the best available device;
- `cpu`: most compatible, slower training;
- `cuda`: NVIDIA GPU;
- `rocm`: AMD GPU;
- `mps`: Apple Silicon.

Fit and small inference work on CPU. Laya fine-tuning should use a GPU.

## 4. Laya Fit + Calibration

### Use Case

- quick baseline;
- moderate dataset;
- compare data versions quickly.

### Steps

1. Open Training.
2. Select a snapshot.
3. Target: Laya.
4. Mode: Fit + calibration.
5. Device: auto.
6. Start training.

Fit uses the training split and ignores epochs, batch, and other fine-tuning parameters.

### Dependency

```bash
FIT_SOURCE=hf ./deploy.sh pull-fit
```

If download fails, set `LAYA_FIT_MODEL` and `LAYA_FIT_BACKBONE` to local directories.

### Result

Fit registers a calibration artifact for evaluation and deployment.

## 5. Laya Fine-Tuning

### Steps

1. Select a snapshot.
2. Target: Laya.
3. Mode: Fine-tune checkpoint.
4. Choose default or multilingual Laya.
5. Configure parameters.
6. Start training.

### Parameters

| Parameter | Default | Description |
|---|---|---|
| Epochs | 4 | 2–6 for small data |
| Micro batch | 8 | Lower if VRAM is limited |
| Gradient accumulation | 8 | Increases effective batch |
| Loss | rlcd | rlcd or soft-ce |
| Freeze encoder | Off | Saves memory, may reduce quality |
| Shuffle options | Off | Improves option-order robustness |

First run:

```text
epochs=4
microBatch=8
gradAccum=8
loss=rlcd
freezeEncoder=false
shuffleOptions=false
```

Low memory:

```text
microBatch=2 or 4
gradAccum=16 or 32
freezeEncoder=true
```

### Training Progress

The page shows progress, stage, device, artifact path, log path, and errors.

Training can be cancelled. Interrupted training must be restarted.

## 6. GLiNER Fine-Tuning

### Use Case

- `GLiNER2.5-Decide` for English;
- `GLiNER2.5-multi-Decide` for Chinese or multilingual;
- lightweight text classification.

### Steps

1. Confirm GLiNER is enabled.
2. Select a snapshot.
3. Target: GLiNER.
4. Choose English or multilingual base.
5. Set epochs, batch, and gradient accumulation.
6. Start training.

GLiNER supports fine-tuning only.

### Limitation

GLiNER returns labels and confidence, not full class probabilities. Evaluation does not compute Brier and marks results confidence-only.

## 7. Evaluation

### Steps

1. Open Evaluation.
2. Select a snapshot.
3. Select a device.
4. Select models.
5. Start evaluation.

### Model Groups

- **Remote baseline:** Jev
- **Base models:** official checkpoints
- **Trained models:** Fit calibration, Laya fine-tune, GLiNER fine-tune

Trained models use the latest artifact by default. Click “More” to evaluate a historical version.

### Evaluation Set

Validation + test held-out rows are used by default. If there is no held-out split, all rows are used with a warning.

### Metrics

| Metric | Meaning |
|---|---|
| Accuracy | Overall accuracy |
| Macro F1 | Balanced class performance |
| MAE | Error for Score questions |
| ECE | Calibration error; lower is better |
| Brier | Probability error; not computed for GLiNER |
| Latency | P50 / P95 response time |

### Reading Results

- High accuracy, low Macro F1: weak long-tail classes.
- High ECE: probabilities are unreliable; add data or calibrate.
- Jev clearly better: not enough data or Schema too complex.
- Fit close to fine-tune: prefer the cheaper Fit.

## 8. Artifacts

On the Models page:

| Type | Source |
|---|---|
| Fit calibration | Laya Fit |
| Laya checkpoint | Laya fine-tune |
| GLiNER checkpoint | GLiNER fine-tune |

Each artifact can:

- download as ZIP;
- be deployed;
- be deleted after stopping its deployment.

The download button shows packaging/progress status and prevents duplicate clicks.

## 9. Playground

Playground tests a single input without writing datasets or jobs.

You can:

- choose a Base or trained model;
- choose a historical model version;
- use the project Schema, presets, or a fully custom Schema;
- enter any valid JSON state;
- inspect answers, confidence, probabilities, and latency;
- export a SystemOne cURL.

### Presets

Three question types are available:

- Noul: Is a hamburger a sandwich?
- Choice: What color is the sky?
- Score: How urgent is the text?

Choose Chinese or English examples, or combine all three.

### Export cURL

Fill in a BaseURL and request model name to generate a complete `/v1/systemone` body. URLs and model names may use placeholders.

## 10. Experiment Advice

1. Freeze snapshot v1.
2. Evaluate Base, Fit, and Jev.
3. Add hard samples and real held-out data.
4. Freeze v2.
5. Retrain and evaluate with the same parameters.
6. Change one variable at a time.

Choose models based on held-out results, not training loss.

## 11. Common Issues

| Problem | Fix |
|---|---|
| Laya runtime missing | `./deploy.sh setup-laya` |
| No Fit artifact | Train Laya Fit first |
| No fine-tuned artifact | Complete Laya fine-tuning |
| GLiNER disabled | Set `GLINER_ENABLED=true` and restart |
| GLiNER cannot Fit | Fine-tune only |
| Out of memory | Lower micro batch and raise accumulation |
| Evaluation uses only some rows | Check `EVAL_MAX_ROWS` |

More help: [Troubleshooting](./troubleshooting.md).
