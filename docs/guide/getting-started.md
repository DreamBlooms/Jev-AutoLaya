# 快速开始

本指南带你从零启动 AutoLaya，并完成第一个领域决策模型。

## 1. 准备环境

确认以下命令可用：

```bash
python3 --version   # 3.12+
node --version      # 20.19+，推荐 22+
npm --version
```

Ubuntu 安装示例：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
# Node.js 请安装 20+ 版本
```

## 2. 安装

在 AutoLaya 目录执行：

```bash
./deploy.sh setup
```

`setup` 会安装依赖、创建 `backend/.env`、构建前端，并准备数据目录。

安装 Laya 运行时：

```bash
./deploy.sh setup-laya
```

需要 GLiNER 时再安装：

```bash
./deploy.sh setup-gliner
```

### GPU 安装

NVIDIA CUDA：

```bash
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-laya
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-gliner
```

AMD ROCm 或 CPU：

```bash
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/rocm6.4 ./deploy.sh setup-laya
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/cpu ./deploy.sh setup-laya
```

请使用与本机驱动匹配的 PyTorch wheel 源。

## 3. 配置 Key

打开 `backend/.env`。如果文件不存在，先运行一次 `./deploy.sh setup`。

### 3.1 LLM

生成数据需要一个 OpenAI-compatible Chat Completions 服务。DeepSeek 是默认配置：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=your_key
```

也可以使用 OpenRouter、OpenAI、vLLM、Ollama 等兼容服务。

### 3.2 Jev Teacher（可选）

OpenRouter：

```env
JEV_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
OPENROUTER_JEV_MODEL=~typesafe/jev-latest
```

TypeSafe：

```env
JEV_PROVIDER=typesafe
TYPESAFE_API_KEY=your_key
TYPESAFE_JEV_MODEL=jev-1.14.0
```

没有 Jev 时，可以在生成页选择“LLM 直接标注”或“不使用 Teacher”。

### 3.3 GLiNER（可选）

```env
GLINER_ENABLED=true
GLINER_BASE_MODEL=fastino/GLiNER2.5-Decide
GLINER_MULTI_MODEL=fastino/GLiNER2.5-multi-Decide
```

### 3.4 重启

```bash
./deploy.sh restart
```

Key 只会被后端读取，不会发送到浏览器。

## 4. 下载模型

基础模型：

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

下载完成后会自动更新 `backend/.env` 中的模型路径。

## 5. 启动

```bash
./deploy.sh start
```

访问：

- Web 界面：<http://localhost:8000>
- API 文档：<http://localhost:8000/docs>
- 健康检查：<http://localhost:8000/api/health>

常用命令：

```bash
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh stop
```

### 检查配置

```bash
curl -s http://localhost:8000/api/v1/config
```

重点查看：

- `llmConfigured`
- `jevConfigured`
- `availableDevices`
- `layaRuntimeReady`
- `glinerRuntimeReady`

“设置”页也会显示这些信息。

## 6. 第一次使用

首次访问会自动显示全流程引导，使用 Mock 数据，不会修改真实项目，可以跳过。之后可以在“设置 → 使用引导”重新查看。

### 6.1 创建项目

1. 点击“新建项目”。
2. 填写项目名称和领域描述。
3. 选择中文、英文或两种语言。

例如：

```text
名称：客服工单分流
领域：SaaS 客服工单，需要判断处理团队和紧急程度
```

### 6.2 定义 Schema

在 Schema 标签添加问题：

- **Choice**：多选一，例如 `team = billing / technical / sales`
- **Noul**：是/否概率，例如“是否需要今天处理”
- **Score**：有序等级，例如“可以等待 / 本周处理 / 今天处理”

问题键名建议使用英文小写，例如 `team`、`urgent`、`priority`。

### 6.3 添加数据

可以：

- 手动添加种子；
- 下载 JSONL/CSV 模板后批量导入种子或样本；
- 用 LLM 生成新的领域文本。

种子应尽量来自真实业务，并覆盖主要标签和边界情况。

### 6.4 生成并标注

在“生成”页设置：

- 样本数量；
- 语言；
- Teacher；
- 简单、中等、困难比例；
- 困难/歧义比例；
- 是否平衡标签。

高级设置可以：

- 追加自定义 Prompt；
- 设置 Think 预算；
- 设置 Think 等级；
- 设置温度；
- 预览完整 LLM 请求体。

生成后的样本需要人工审核。

### 6.5 人工审核

在审核队列中：

1. 查看样本和教师答案；
2. 修改 Choice、Noul、Score；
3. 保存答案；
4. 补全所有问题后接受；
5. 不需要的样本可以拒绝。

可以勾选多条进行批量处理。

### 6.6 冻结数据集

在“数据集”标签点击“冻结快照”。

快照只包含已接受且每个问题都有答案的样本，可下载：

- Canonical JSONL
- Laya JSONL
- GLiNER JSONL

### 6.7 训练

在“训练”标签：

1. 选择快照；
2. 选择目标模型和具体 Base；
3. 选择 Fit 或微调；
4. 选择设备；
5. 设置参数；
6. 开始训练。

第一次建议先做 Laya Fit，得到基线后再考虑微调。

### 6.8 评估

在“评估”标签选择快照和模型。评估页会按以下分组显示：

- 远程基线
- Base 模型
- 已训练模型

已训练模型可以点击“更多”选择历史版本。

### 6.9 Playground

Playground 可以不创建任务就测试单条输入：

- 选择 Base 或已训练模型；
- 使用项目 Schema、预置题目或完全自定义 Schema；
- 输入任意合法 JSON State；
- 查看每个问题的答案和概率；
- 导出 SystemOne cURL。

### 6.10 部署

在“模型”页选择产物并部署。启动后会得到一个本地地址，例如：

```text
http://127.0.0.1:8100/v1/systemone
```

详细请求格式见 [部署与 API](./deployment-api.md)。

## 7. 数据与备份

默认数据位于：

```text
data/
├── autolaya.db
├── datasets/
└── artifacts/
```

需要备份：

- `backend/.env`
- `data/autolaya.db`
- `data/datasets/`
- `data/artifacts/`
- `models/`（如果不想重新下载）

## 下一步

- [项目与数据流程](./project-workflow.md)
- [训练与评估](./training-evaluation.md)
- [部署与 API](./deployment-api.md)
