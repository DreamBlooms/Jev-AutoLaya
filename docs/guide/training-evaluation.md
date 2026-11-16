# 训练与评估

本指南说明如何把数据集训练成 Laya 或 GLiNER 模型，并在留出集上比较效果。

## 1. 选择训练方式

| 方式 | 目标 | 速度 | 适用场景 |
|---|---|---|---|
| Laya Fit + 校准 | Laya | 快 | 快速建立基线 |
| Laya 微调 | Laya | 慢 | 数据较多、效果优先 |
| GLiNER 微调 | GLiNER2.5 | 中等 | 文本分类，英文或多语言 |

建议顺序：

```text
先做 Laya Fit
  → 评估
  → 再做 Laya 微调
  → 使用同一留出集比较
  → 选择满足要求的模型部署
```

## 2. 训练前准备

确认：

- 已经有冻结的数据集快照；
- 快照包含已接受且完整标注的样本；
- 有真实留出样本；
- 训练集和测试集没有同源泄漏；
- 对应运行时已经安装。

Laya：

```bash
./deploy.sh setup-laya
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf ./deploy.sh pull-fit   # Fit 需要
```

GLiNER：

```bash
./deploy.sh setup-gliner
MODEL_SOURCE=hf MODEL_SET=base ./deploy.sh pull-models
```

并在 `backend/.env` 设置：

```env
GLINER_ENABLED=true
```

“设置”页会显示运行时是否就绪。

## 3. 设备选择

- `auto`：自动选择可用设备；
- `cpu`：兼容性最好，但训练较慢；
- `cuda`：NVIDIA GPU；
- `rocm`：AMD GPU；
- `mps`：Apple Silicon。

Fit 和小模型推理可以在 CPU 上运行。Laya 全量微调建议使用 GPU。

## 4. Laya Fit + 校准

### 适用场景

- 快速建立基线；
- 数据量中等；
- 想快速比较不同数据版本。

### 操作

1. 打开项目的“训练”标签；
2. 选择快照；
3. 目标选择 Laya；
4. 模式选择“Fit + 校准”；
5. 设备选择 auto；
6. 点击“开始训练”。

Fit 使用训练划分，不读取 epochs、batch 等微调参数。

### 依赖

Fit 需要 Vega-U 和 Qwen reader：

```bash
FIT_SOURCE=hf ./deploy.sh pull-fit
```

如果下载失败，可以手动下载后把 `LAYA_FIT_MODEL` 和 `LAYA_FIT_BACKBONE` 指向本地目录。

### 结果

训练完成后会生成“Fit 校准”产物，可用于评估和部署。

## 5. Laya 微调

### 操作

1. 选择快照；
2. 目标选择 Laya；
3. 模式选择“微调 checkpoint”；
4. 选择 Laya 默认版或多语言版；
5. 设置参数；
6. 开始训练。

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| Epochs | 4 | 训练轮数；小数据 2–6 |
| Micro batch | 8 | 显存不足时降低 |
| 梯度累积 | 8 | 增大等效 batch |
| Loss | rlcd | 可选 rlcd / soft-ce |
| 冻结编码器 | 关闭 | 降低显存，但可能影响效果 |
| 打乱选项 | 关闭 | 增强选项顺序鲁棒性 |

第一次建议：

```text
epochs=4
microBatch=8
gradAccum=8
loss=rlcd
freezeEncoder=false
shuffleOptions=false
```

显存不足：

```text
microBatch=2 或 4
gradAccum=16 或 32
freezeEncoder=true
```

### 训练过程

页面会显示进度、当前阶段、设备、产物路径、日志路径和错误信息。

训练任务可以取消。中断的训练需要重新发起。

## 6. GLiNER 微调

### 适用场景

- 英文使用 `GLiNER2.5-Decide`；
- 中文或多语言使用 `GLiNER2.5-multi-Decide`；
- 需要较轻量的分类模型。

### 操作

1. 确认 GLiNER 已启用；
2. 选择快照；
3. 目标选择 GLiNER；
4. 选择英文或多语言 Base；
5. 设置 epochs、batch 和梯度累积；
6. 开始训练。

GLiNER 只支持微调。

### 限制

GLiNER 返回标签和置信度，不提供完整类别概率，因此评估中不会计算 Brier，并会标记为 confidence-only。

## 7. 评估

### 操作

1. 打开“评估”标签；
2. 选择快照；
3. 选择设备；
4. 勾选要比较的模型；
5. 点击“开始评估”。

### 模型分组

评估页把模型分为：

- **远程基线**：Jev
- **Base 模型**：官方基础模型
- **已训练模型**：Fit 校准、Laya 微调、GLiNER 微调

已训练模型默认使用最新产物。点击“更多”可以选择历史版本。

### 评估集

默认使用 validation + test 留出数据；没有留出划分时使用全部数据，并显示提醒。

### 指标

| 指标 | 含义 |
|---|---|
| Accuracy | 准确率 |
| Macro F1 | 类别均衡时的综合表现 |
| MAE | Score 问题的平均误差 |
| ECE | 校准误差，越低越好 |
| Brier | 概率误差，GLiNER 不计算 |
| 延迟 | P50 / P95 响应时间 |

### 如何看结果

- Accuracy 高但 Macro F1 低：长尾类别表现差。
- ECE 高：概率不可信，需要更多数据或校准。
- Jev 明显更好：数据量不足或 Schema 太复杂。
- Fit 和微调接近：优先选择成本更低的 Fit。

## 8. 模型产物

在“模型”页可以看到：

| 类型 | 来源 |
|---|---|
| Fit 校准 | Laya Fit |
| Laya checkpoint | Laya 微调 |
| GLiNER checkpoint | GLiNER 微调 |

每个产物可以：

- 下载 ZIP；
- 部署；
- 删除（先停止部署）。

下载时按钮会显示打包和下载状态，并防止重复点击。

## 9. Playground

Playground 用来快速测试单条输入，不会写入数据集或任务记录。

可以：

- 选择 Base 或已训练模型；
- 选择历史模型版本；
- 使用项目 Schema、预置题目或完全自定义 Schema；
- 输入任意合法 JSON State；
- 查看每个问题的答案、置信度、概率和延迟；
- 导出 SystemOne cURL。

### 预置题目

提供三种题型的例子：

- 判断：汉堡是三明治吗？
- 选择：天空是什么颜色的？
- 评分：这段文本有多紧急？

可以选择中文或英文示例，也可以组合三种题型。

### 导出 cURL

填写 BaseURL 和请求模型名后，可以生成完整的 `/v1/systemone` 请求体。URL 和模型名可以使用占位符。

## 10. 训练建议

1. 先冻结 v1 快照；
2. 评估 Base、Fit 和 Jev；
3. 补充困难样本和真实留出数据；
4. 冻结 v2；
5. 用相同参数重新训练和评估；
6. 每次只调整一个变量。

正式选择模型时，不要只看训练损失，要以留出集结果为准。

## 11. 常见问题

| 问题 | 处理 |
|---|---|
| Laya 运行时未安装 | `./deploy.sh setup-laya` |
| 没有 Fit 产物 | 先训练 Laya Fit |
| 没有微调产物 | 先完成 Laya 微调 |
| GLiNER 未启用 | 设置 `GLINER_ENABLED=true` 并重启 |
| GLiNER 不能 Fit | GLiNER 只支持微调 |
| 显存不足 | 降低 micro batch，增大梯度累积 |
| 评估只取部分数据 | 检查 `EVAL_MAX_ROWS` |

更多问题见 [故障排查](./troubleshooting.md)。
