# AutoLaya 当前状态

> 更新时间：2026-11-16

## 已提供

- 项目、Choice / Noul / Score Schema、种子、样本导入和审核队列。
- LLM 数据生成，支持自定义 Prompt、Think 预算、Think 等级、温度和请求预览。
- Jev Teacher、LLM 直接标注和人工标注。
- 不可变数据集快照，支持 Canonical、Laya、GLiNER JSONL 下载和删除。
- Laya Fit + 校准、Laya 微调、GLiNER2.5 微调。
- 留出集评估，支持 Base、Fit、微调模型和历史训练版本。
- 模型产物 ZIP 下载和本地部署。
- Playground：自定义 Schema/State，测试 Base 和已训练模型，导出 SystemOne cURL。
- 首次访问引导、深浅色主题和中英文界面。
- 本地 `deploy.sh` 部署，无需 Docker。

## 已验证

- DeepSeek 生成中英文数据。
- Jev 通过 OpenRouter 完成真实标注。
- Laya Fit、Laya 微调、GLiNER 英文和多语言完成训练、评估和部署。
- 本地模型服务可调用 `/v1/systemone` 和 `/v1/classify`。
- Playground 可测试 Base 和指定历史 checkpoint。

## 已知限制

- 管理页面没有内置鉴权，不能直接公开到公网。
- 不支持多标签决策；请拆成多个 Noul 问题。
- GLiNER 只提供置信度，不提供完整校准概率。
- 暂不支持 SystemOne 图片 assets。

## 适合的使用方式

- 本地或内网部署。
- 人工审核作为最终质量关口。
- 用真实留出数据做最终评估。
- 先用 Laya Fit 建立基线，再决定是否微调。
