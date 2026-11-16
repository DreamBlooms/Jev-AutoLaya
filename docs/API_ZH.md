# AutoLaya API 参考

> 安装、UI 操作和部署示例请先阅读 [用户指南](guide/README.md)。

Base URL: `http://localhost:8000/api/v1`

浏览器 API 字段使用 camelCase，数据库标识使用 UUID 字符串。

> **鉴权：** 管理 API 没有内置鉴权，请勿暴露到公网。详见 [部署与 API](guide/deployment-api.md#6-鉴权)。

---

## 运行时配置

### `GET /config`

```json
{
  "data": {
    "device": "cpu",
    "availableDevices": ["cpu", "cuda"],
    "cpu": {
      "name": "AMD Ryzen 9 7950X 16-Core Processor",
      "logicalCores": 32
    },
    "memory": {
      "totalMb": 65536,
      "availableMb": 32768
    },
    "dataDir": "/path/to/AutoLaya/data",
    "modelsDir": "/path/to/AutoLaya/models",
    "artifactDir": "/path/to/AutoLaya/data/artifacts",
    "gpuDevices": [
      {
        "vendor": "NVIDIA",
        "backend": "cuda",
        "name": "NVIDIA GeForce RTX 4090",
        "memoryTotalMb": 24564,
        "memoryUsedMb": 1024,
        "driver": "580.65",
        "computeCapability": "8.9"
      }
    ],
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

支持：`auto`、`cpu`、`cuda`、`mps`、`rocm`。

---

## Projects

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/projects` | 创建领域项目 |
| GET | `/projects` | 项目列表 |
| GET | `/projects/{id}` | 项目详情 |
| PUT | `/projects/{id}` | 更新项目 |
| POST | `/projects/{id}/delete` | 删除项目 |

### 创建项目

```json
{
  "name": "工单路由",
  "domain": "客服工单",
  "languages": ["zh", "en"]
}
```

---

## Question Schemas

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/projects/{id}/questions` | 添加 Choice/Noul/Score |
| GET | `/projects/{id}/questions` | 题目列表 |
| PUT | `/projects/{id}/questions/{qid}` | 更新题目 |
| DELETE | `/projects/{id}/questions/{qid}` | 删除题目 |

### Choice

```json
{
  "key": "team",
  "type": "choice",
  "instructions": "这条工单应该由哪个团队处理？",
  "criteria": {
    "billing": "退款、发票、支付",
    "technical": "Bug、故障、API 问题",
    "sales": "价格、试用、报价"
  }
}
```

### Noul

```json
{
  "key": "urgent",
  "type": "noul",
  "instructions": "这条工单需要今天处理吗？"
}
```

### Score

```json
{
  "key": "urgency",
  "type": "score",
  "instructions": "这条工单有多紧急？",
  "criteria": ["可以等待", "本周处理", "今天处理"]
}
```

---

## Seeds 与 Prompt

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/projects/{id}/seeds` | 导入种子样本 |
| POST | `/projects/{id}/heldout` | 导入真实留出样本（固定 test 划分） |
| GET | `/projects/{id}/seeds` | 种子列表 |
| GET | `/projects/{id}/seeds/template?format=jsonl` | 下载 JSONL 种子模板 |
| GET | `/projects/{id}/seeds/template?format=csv` | 下载 CSV 种子模板 |
| POST | `/projects/{id}/seeds/import` | 上传 JSONL/CSV（`multipart/form-data`，字段 `file`） |
| DELETE | `/seeds/{id}` | 删除种子 |
| POST | `/projects/{id}/schema-suggestions` | LLM 生成题目建议 |
| POST | `/projects/{id}/generation-prompts` | 保存 Prompt 模板 |

---

## 数据生成

### `POST /projects/{id}/generate`

```json
{
  "count": 500,
  "languages": ["zh", "en"],
  "difficulty": { "easy": 0.5, "medium": 0.35, "hard": 0.15 },
  "negativeRatio": 0.1,
  "labelBalanced": true,
  "teacher": "jev",
  "customPrompt": "优先生成简短、真实的客服工单。",
  "systemPromptTemplate": "你是 {{project_name}} 领域的生成器，使用 {{language}} 输出。",
  "userPromptTemplate": "根据 {{schema_json}} 和 {{seeds_json}} 生成 {{count}} 条样本。",
  "llm": {
    "baseUrl": "https://api.deepseek.com",
    "model": "deepseek-flash",
    "temperature": 0.7,
    "thinkBudget": 512,
    "thinkLevel": "medium"
  }
}
```

`teacher` 可选 `jev`、`llm`、`none` 或 `human`。使用 `llm` 时，同一次生成请求会让 LLM 同时输出弱标签，写入 `teacher=llm`，样本仍必须经过人工审核。`customPrompt` 会追加到生成指令末尾，不改变 JSON 输出结构。`thinkBudget` 会写入 `reasoning.max_tokens`，`thinkLevel` 会写入 `reasoning_effort`，仅对支持这些参数的 Provider 生效。预览接口返回实际模型、端点、语言、批大小和完整 Chat Completions 请求体。

可用 Prompt 占位符：`project_name`、`project_domain`、`language`、`count`、`difficulty`、`negative_ratio`、`schema_json`、`seeds_json`、`sample_shape`、`label_rule`、`label_instruction`、`balancing`、`negative_instruction`、`default_system`、`default_user`、`custom_prompt`。自定义模板会完全替换默认内容；使用 `default_system` / `default_user` 可以复用默认内容。

返回：`202` + `GenerationJob`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/generation-jobs/{id}` | 任务状态 |
| GET | `/generation-jobs/{id}/events` | SSE 进度 |
| POST | `/generation-jobs/{id}/pause` | 暂停 |
| POST | `/generation-jobs/{id}/resume` | 恢复 |
| POST | `/generation-jobs/{id}/cancel` | 取消 |

SSE 示例：

```text
data: {"stage":"generating","completed":120,"total":500}
data: {"stage":"labeling","completed":80,"total":500}
data: {"stage":"filtering","completed":500,"total":500}
data: {"stage":"completed","accepted":421,"rejected":79}
```

---

## Samples 与标注

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/samples?status=pending&projectId=` | 审核队列 |
| GET | `/samples/{id}` | 样本与标注 |
| POST | `/samples/{id}/accept` | 通过 |
| POST | `/samples/{id}/reject` | 拒绝 |
| PUT | `/samples/{id}/annotations/{qid}` | 修改答案 |
| POST | `/samples/{id}/reannotate` | 重新教师标注 |
| GET | `/projects/{id}/samples/template?format=jsonl` | 下载 JSONL 模板 |
| GET | `/projects/{id}/samples/template?format=csv` | 下载 CSV 模板 |
| POST | `/projects/{id}/samples/import` | 上传 JSONL/CSV（`multipart/form-data`，字段 `file`） |

批量导入列：

```text
state,labels,language,difficulty,heldout
```

`state` 是 JSON 对象（也可以是普通字符串，会存为 `{"text": "..."}`）；`labels` 是问题键到答案的 JSON 对象；`heldout` 支持 `true/false/1/0/yes/no`。响应返回 `imported`、`heldout` 和创建的样本。

### 标注结构

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

## 数据集

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/projects/{id}/datasets` | 冻结数据集快照 |
| GET | `/datasets/{id}` | 快照统计 |
| DELETE | `/datasets/{id}` | 删除快照记录和导出文件 |
| GET | `/datasets/{id}/download?format=canonical` | 下载 Canonical JSONL |
| GET | `/datasets/{id}/download?format=laya` | 下载 Laya JSONL |
| GET | `/datasets/{id}/download?format=gliner` | GLiNER JSONL |

返回包括训练/校准/验证/测试数量和标签分布。存在 pending/running 的训练或评估任务时禁止删除快照。相关训练/评估记录会一并删除，模型产物保留。新快照版本使用 `max(现有版本) + 1`。

---

## 训练

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

`target`：`laya` 或 `gliner`。  
`mode`：`fit` 或 `finetune`。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/training-jobs` | 任务列表 |
| GET | `/training-jobs/{id}` | 任务详情 |
| GET | `/training-jobs/{id}/events` | SSE 进度 |
| POST | `/training-jobs/{id}/cancel` | 取消 |

---

## 评估

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

`artifactIds` 可选，用于为 `laya-fit`、`laya-finetuned` 或 `gliner-finetuned` 指定历史产物；未指定的键使用该类型最新产物。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/evaluations/{id}` | 结果 |
| GET | `/evaluations/{id}/report` | 下载 JSON/Markdown 报告 |

`results.modelInfo` 记录每个模型的角色（`remote`、`base`、`fit`、`finetuned`）、目标、来源，以及精确的产物元数据（名称、路径、类型、创建时间），保证历史评估可追溯。

---

## 操练场

### `POST /playground/run`

使用 Base 模型或已训练产物运行单条输入，不写入任何数据集或任务记录。

```json
{
  "projectId": "uuid",
  "model": "laya-finetuned",
  "artifactId": "artifact-uuid",
  "state": {"ticket": "我这个月被重复扣款了。"},
  "questions": [
    {
      "key": "team",
      "type": "choice",
      "instructions": "这条工单应该由哪个团队处理？",
      "criteria": {"billing": "退款与支付", "technical": "Bug 与故障"}
    },
    {
      "key": "urgent",
      "type": "noul",
      "instructions": "需要今天处理吗？",
      "criteria": {"true": "需要今天处理", "false": "可以等待"}
    },
    {
      "key": "priority",
      "type": "score",
      "instructions": "优先级是多少？",
      "criteria": ["可以等待", "本周处理", "今天处理"]
    }
  ],
  "device": "auto"
}
```

提供 `questions` 时 `projectId` 可以省略；已训练产物仍需项目。`state` 支持字符串、对象或数组。省略 `questions` 时使用项目当前 Schema，提供时使用完全自定义 Schema。

`model` 支持 `laya-base`、`laya-multi-base`、`laya-fit`、`laya-finetuned`、`gliner-base`、`gliner-multi-base`、`gliner-finetuned`。已训练模型可以传 `artifactId` 指定历史版本，省略时使用该类型最新产物。响应包含 `modelInfo`、`answers`、`latencyMs`、`routing`、`usage`。

SystemOne 的 `assets` 仅用于图片，本地文本运行时暂不支持，因此操练场不提供 assets 编辑，也不会写入导出的 cURL。

---


## 模型产物

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/artifacts` | 列出 fit / 微调产物 |
| GET | `/artifacts/{id}` | 产物元数据与指标 |
| GET | `/artifacts/{id}/download` | 以 ZIP 下载产物目录 |
| DELETE | `/artifacts/{id}` | 删除产物（不能有运行中的部署） |

## 部署

```json
{
  "artifactId": "uuid",
  "target": "laya",
  "host": "127.0.0.1",
  "port": 8100
}
```

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/deployments` | 启动模型服务 |
| GET | `/deployments` | 实例列表 |
| GET | `/deployments/{id}` | 状态/健康检查 |
| POST | `/deployments/{id}/stop` | 停止 |
| POST | `/deployments/{id}/restart` | 重启 |
| DELETE | `/deployments/{id}` | 停止并删除部署 |

Fit 校准产物和微调 checkpoint 都可以部署。Laya 提供 Jev 兼容接口：

```text
POST /v1/systemone
POST /v1/systemone/batch
GET  /health
```

GLiNER 部署提供 `/v1/classify` 和 Jev 兼容的 `/v1/systemone` 映射。

## 任务事件与取消

```text
GET  /generation-jobs/{id}/events
GET  /training-jobs/{id}/events
GET  /evaluations/{id}/events
POST /generation-jobs/{id}/cancel
POST /training-jobs/{id}/cancel
POST /evaluations/{id}/cancel
```

事件使用 `text/event-stream`，字段与任务响应一致。

---

## 错误格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "..."
  }
}
```

常见错误码：

- `VALIDATION_ERROR`
- `NOT_FOUND`
- `PROVIDER_ERROR`
- `LLM_ERROR`
- `TEACHER_ERROR`
- `TRAINING_ERROR`
- `DEPLOYMENT_ERROR`
- `RESERVED_TARGET`
- `SNAPSHOT_IN_USE`
