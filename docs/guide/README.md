# AutoLaya 用户指南

欢迎使用 AutoLaya。本指南面向实际使用者，按“安装 → 准备数据 → 训练 → 评估 → 部署”的顺序说明如何完成一个领域决策模型。

AutoLaya 不会要求你写训练脚本。你只需要在 Web 界面中定义问题、准备样例、审核数据，然后选择模型并开始训练。

## 指南目录

| 文档 | 内容 |
|---|---|
| [快速开始](./getting-started.md) | 安装、配置、启动和第一个项目 |
| [项目与数据流程](./project-workflow.md) | 项目、Schema、种子、生成、审核、数据集 |
| [训练与评估](./training-evaluation.md) | Laya、GLiNER、模型评估、模型产物、Playground |
| [部署与 API](./deployment-api.md) | 启动模型服务、调用接口、备份和安全 |
| [故障排查](./troubleshooting.md) | 常见问题和处理方式 |

English guide: [English](./en/README.md)

## 系统要求

| 资源 | 最低配置 | 推荐配置 |
|---|---|---|
| 操作系统 | Ubuntu 20.04+ / macOS 12+ | Linux |
| Python | 3.12+ | 3.12 / 3.13 |
| Node.js | 20.19+ | 22+ |
| 内存 | 16 GB | 32 GB+ |
| 存储 | 30 GB 可用空间 | 100 GB+ |
| GPU | 可选 | NVIDIA CUDA / AMD ROCm |
| 浏览器 | 最新版 Chrome / Edge / Firefox | Chrome |

不需要 Docker、PostgreSQL 或外部数据库。默认使用 SQLite，数据保存在 `data/`。

## 完整流程

```text
创建项目
  → 定义 Schema
  → 添加种子或导入数据
  → 生成领域文本
  → 标注与人工审核
  → 冻结数据集
  → 训练 Laya / GLiNER
  → 在留出集上评估
  → 部署本地 API
```

## 主要功能

- **项目与 Schema**：一个项目对应一个领域和一组决策问题。
- **三种题型**：Choice（单选）、Noul（是/否概率）、Score（有序评分）。
- **数据准备**：手动添加、JSONL/CSV 模板导入、LLM 生成、真实留出数据。
- **自动标注**：Jev Teacher、LLM 弱标注、人工标注。
- **人工审核**：逐条或批量接受、拒绝、修改答案。
- **数据集版本**：冻结快照，下载 Canonical、Laya、GLiNER JSONL。
- **训练**：Laya Fit、Laya 微调、GLiNER2.5 微调。
- **评估**：对比 Base、Fit、微调模型，并选择历史训练版本。
- **Playground**：自由编辑 Schema/State，测试 Base 和已训练模型，导出 SystemOne cURL。
- **部署**：本地模型服务，提供 Jev 兼容接口。

## 两种模型

### Laya

适合文本决策。可以先做 Fit 快速得到基线，也可以做全量微调获得更好的效果。支持默认版和多语言版。

### GLiNER2.5-Decide

适合文本分类，英文使用默认版，多语言使用 multi 版。只支持微调，只返回标签和置信度。

## 核心概念

| 概念 | 说明 |
|---|---|
| 项目 | 一个领域和一套决策 Schema |
| Schema | 一组 Choice / Noul / Score 问题 |
| 种子 | 用来锚定领域语言和标签的真实样例 |
| 样本 | 一条待审核或已审核的领域文本 |
| 快照 | 某个时间点冻结的数据集版本 |
| 模型产物 | Fit 校准、Laya checkpoint 或 GLiNER checkpoint |
| 部署 | 由模型产物启动的本地服务 |

## 推荐阅读顺序

1. 第一次使用：[快速开始](./getting-started.md)
2. 准备正式数据：[项目与数据流程](./project-workflow.md)
3. 训练和评估：[训练与评估](./training-evaluation.md)
4. 接入业务：[部署与 API](./deployment-api.md)
5. 遇到问题：[故障排查](./troubleshooting.md)

## 获取帮助

- 页面内 API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/api/health`
- 完整接口参考：[API 参考](../API_ZH.md)
- 当前功能和限制：[当前状态](../STATUS_ZH.md)
