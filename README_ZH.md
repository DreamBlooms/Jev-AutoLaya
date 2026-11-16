# AutoLaya

[English](README.md) | 简体中文

**AutoLaya** 是一个本地优先的领域决策模型构建工具。它把领域描述和少量真实样例，变成可以自己训练、评估并部署的 Laya 或 GLiNER 决策模型。

<img width="1920" height="980" alt="图片" src="https://github.com/user-attachments/assets/efc029f7-eb6e-4da3-a964-c6ca22aebb05" />

```text
领域描述 / 种子样例
        → LLM 生成领域文本
        → Jev / LLM / 人工标注
        → 人工审核
        → 冻结数据集
        → 训练 Laya / GLiNER
        → 在留出集上评估
        → 部署本地决策 API
```

<img width="1920" height="980" alt="图片" src="https://github.com/user-attachments/assets/7a89e6c0-69d0-483d-9364-891d5963b6e2" />

整个流程都在一个 Web 工作台里完成，不需要写训练脚本，也不需要把业务数据发送到托管训练平台。

## 你可以做什么

- **定义领域和 Schema**：用 Choice、Noul、Score 描述要做的决策。
- **准备数据**：手动添加、JSONL/CSV 批量导入、用 LLM 生成，或用真实留出样本评估。
- **自动标注**：使用 Jev Teacher、LLM 弱标注或完全人工标注。
- **人工审核**：逐条修改、接受、拒绝，也可以批量处理。
- **管理数据集**：冻结不可变快照，下载 Canonical、Laya、GLiNER JSONL。
- **训练模型**：Laya Fit + 校准、Laya 微调、GLiNER2.5 微调。
- **评估模型**：对比 Base、Fit、微调模型，可选择历史训练版本。
- **测试模型**：在 Playground 中自由编辑 Schema 和 State，测试不同模型。
- **部署模型**：启动本地模型服务，调用 Jev 兼容的 `/v1/systemone`。
- **导出请求**：从 Playground 生成完整的 SystemOne cURL 请求。

## 快速开始

环境要求：

- Python 3.12+
- Node.js 20.19+（推荐 22+）
- 16 GB 内存；训练建议 32 GB+
- GPU 可选：NVIDIA CUDA 或 AMD ROCm；CPU 也能运行 Fit 和推理

安装并启动：

```bash
./deploy.sh setup
./deploy.sh setup-laya
./deploy.sh setup-gliner   # 需要 GLiNER 时执行
./deploy.sh start
```

打开 <http://localhost:8000>。API 文档位于 <http://localhost:8000/docs>。

首次访问会自动显示全流程引导。引导使用 Mock 数据，不会修改真实项目，可以随时在“设置 → 使用引导”中重新打开。

### 配置 Key

`deploy.sh` 会自动创建 `backend/.env`。在这里填写 LLM 和 Jev 的 Key：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=your_key

# 使用 OpenRouter 的 Jev
JEV_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_JEV_MODEL=~typesafe/jev-latest
```

也可以使用任意 OpenAI-compatible Chat Completions 服务。没有 Jev 时，可以选择“LLM 直接标注”或“不使用 Teacher”。

修改后重启：

```bash
./deploy.sh restart
```

### 下载模型

Laya 和 GLiNER 基础模型：

```bash
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
MODEL_SOURCE=hf-mirror MODEL_SET=base ./deploy.sh pull-models
MODEL_SOURCE=ms MODEL_SET=base ./deploy.sh pull-models
```

Laya Fit 模型：

```bash
FIT_SOURCE=hf ./deploy.sh pull-fit
FIT_SOURCE=hf-mirror ./deploy.sh pull-fit
FIT_SOURCE=hf FIT_BACKBONE_SOURCE=ms ./deploy.sh pull-fit
```

### GPU

NVIDIA CUDA：

```bash
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-laya
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-gliner
```

AMD ROCm 或纯 CPU 请使用匹配的 PyTorch wheel 源：

```bash
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/rocm6.4 ./deploy.sh setup-laya
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/cpu ./deploy.sh setup-laya
```

## 第一次使用

1. 打开 AutoLaya，看完首次引导。
2. 新建项目，填写领域和语言。
3. 在 Schema 中添加 Choice、Noul 或 Score 问题。
4. 添加种子，或使用模板批量导入 JSONL/CSV。
5. 生成数据并审核。
6. 冻结数据集。
7. 训练 Laya 或 GLiNER。
8. 在评估页比较模型，在 Playground 中自由测试。
9. 在模型页部署，得到本地 `/v1/systemone` 地址。

详细步骤见 [快速开始](docs/guide/getting-started.md)。

## 文档

| 文档 | 内容 |
|---|---|
| [用户指南](docs/guide/README.md) | 完整使用说明和操作步骤 |
| [快速开始](docs/guide/getting-started.md) | 安装、配置、启动和第一个项目 |
| [项目与数据流程](docs/guide/project-workflow.md) | Schema、种子、生成、审核和数据集 |
| [训练与评估](docs/guide/training-evaluation.md) | Laya、GLiNER、评估、模型产物和 Playground |
| [部署与 API](docs/guide/deployment-api.md) | 部署、调用接口、备份和安全 |
| [故障排查](docs/guide/troubleshooting.md) | 常见问题和处理方法 |
| [API 参考](docs/API_ZH.md) | 面向集成的完整接口说明 |
| [设计文档](docs/DESIGN_ZH.md) | 架构与设计记录 |

## 运维

```bash
./deploy.sh start
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh stop
```

备份时至少保留：

- `backend/.env`
- `data/autolaya.db`
- `data/datasets/`
- `data/artifacts/`
- `models/`（如果不想重新下载）

## 已知限制

- 管理 API 没有内置登录鉴权，请勿直接暴露到公网。
- 暂不支持多标签决策；可以拆成多个 Noul 问题。
- GLiNER 只提供标签和置信度，不提供完整校准概率。
