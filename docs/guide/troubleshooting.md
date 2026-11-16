# 故障排查

先运行：

```bash
./deploy.sh status
./deploy.sh logs
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/v1/config
```

## 1. 服务无法启动

现象：

```text
AutoLaya did not become healthy
```

检查：

```bash
tail -n 100 deploy.log
./deploy.sh status
ss -ltnp | grep 8000
```

常见原因：

| 原因 | 处理 |
|---|---|
| 8000 端口被占用 | 停止占用进程，或使用 `BACKEND_PORT=8001 ./deploy.sh start` |
| 依赖未安装 | 重新运行 `./deploy.sh setup` |
| 前端未构建 | `./deploy.sh build` |
| 数据目录不可写 | 修复 `data/` 权限 |
| Python 版本过低 | 安装 Python 3.12+ |

## 2. 页面空白或刷新 404

处理：

```bash
./deploy.sh build
./deploy.sh restart
```

不要直接打开 `frontend/index.html`，请访问 `http://localhost:8000`。

## 3. LLM 未配置

现象：

- 生成按钮不可用；
- 页面提示未配置 `LLM_API_KEY`；
- `llmConfigured: false`。

检查：

```bash
grep -n 'LLM_' backend/.env
```

确认：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_API_KEY=your_key
```

修改后：

```bash
./deploy.sh restart
```

## 4. LLM 调用失败

| 错误 | 处理 |
|---|---|
| 401 / 403 | Key 错误或无权限 |
| 404 | Base URL 或模型名错误 |
| 429 | 触发限流，降低并发或等待 |
| Timeout | 增大超时或换更快的模型 |
| 返回非 JSON | 换支持 JSON 输出的模型 |
| 余额不足 | 充值或切换 Provider |

可以降低：

```env
LLM_MAX_CONCURRENCY=1
GENERATION_BATCH_SIZE=5
```

## 5. Jev 未配置或标注失败

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

修改后重启。没有 Jev 时可以使用 LLM 直接标注或人工标注。

## 6. 生成任务暂停、卡住或中断

- 生成任务支持暂停和继续；
- 服务重启后，排队任务会继续；
- 运行中的任务可能需要重新发起；
- 已生成的样本不会丢失。

如果一直没有样本：

- 检查模型是否返回空内容；
- 检查是否全部被判定为重复；
- 检查 Teacher 是否持续失败；
- 查看 `deploy.log`。

## 7. 没有待审核样本

检查：

- 生成任务是否完成；
- 样本状态是否为 `pending`；
- 审核页是否筛选了其他项目；
- 是否已经批量处理。

## 8. 无法接受样本

接受前必须为每个问题填写答案。

如果 Teacher 只返回了部分问题，或者后来新增了问题，需要手动补全后再接受。

## 9. 冻结数据集失败

### `No accepted samples are available`

没有已接受样本，请先审核。

### `Accepted samples are missing accepted answers`

某些已接受样本缺少答案，请补全并重新接受。

### `Add at least one question before freezing a dataset`

项目没有 Schema，请先添加问题。

### 没有 test / validation

数据太少时无法保证三部分都有。请增加样本或添加真实留出样本。

## 10. Laya 运行时未安装

```bash
./deploy.sh setup-laya
```

检查：

```bash
ls backend/laya-venv/bin/python
ls backend/laya-venv/bin/laya-train
ls backend/laya-venv/bin/laya-serve
```

GPU 安装失败时使用匹配的 wheel 源：

```bash
CUDA_TORCH_INDEX=https://download.pytorch.org/whl/cu128 ./deploy.sh setup-laya
LAYA_TORCH_INDEX=https://download.pytorch.org/whl/rocm6.4 ./deploy.sh setup-laya
```

## 11. Laya Fit 失败

检查：

```bash
grep -n 'LAYA_FIT_' backend/.env
ls -la /path/to/vega-U
ls -la /path/to/Qwen3.5-0.8B
```

没有模型时：

```bash
FIT_SOURCE=hf ./deploy.sh pull-fit
```

Fit 不使用 epochs 等参数，不要通过调 epochs 解决 Fit 失败。

## 12. Laya 微调失败

| 原因 | 处理 |
|---|---|
| 找不到 `laya-train` | 重新安装 Laya 运行时 |
| Base 模型下载失败 | 使用 `pull-models` 或本地路径 |
| 显存不足 | 降低 micro batch，增大梯度累积 |
| 训练中断 | 重新发起训练 |
| 磁盘空间不足 | 清理旧产物 |

显存不足时尝试：

```text
microBatch=2
gradAccum=32
freezeEncoder=true
```

## 13. GLiNER 未启用或训练失败

```bash
./deploy.sh setup-gliner
```

```env
GLINER_ENABLED=true
```

重启后确认“设置”页显示 GLiNER 已就绪。

GLiNER 只支持微调，不支持 Fit。如果快照没有 GLiNER 导出，请重新冻结。

## 14. 评估失败

- `Laya Fit` 需要 Fit 校准产物；
- `Laya 微调` 需要 Laya checkpoint；
- `GLiNER 微调` 需要 GLiNER checkpoint。

先完成对应训练。

如果只评估了部分数据，检查 `EVAL_MAX_ROWS`。

GLiNER 不计算 Brier，这是正常现象。

## 15. Playground 失败

- 选择已训练模型时必须先选择项目；
- Base 模型可以不选项目；
- 自定义 Schema 中 Choice 必须有选项，Score 必须有标签；
- State 必须是字符串、对象或数组；
- 首次加载模型可能需要 10–60 秒。

SystemOne `assets` 图片参数暂不支持，因此 Playground 不提供。

## 16. 部署失败

### 端口被占用

停止旧部署，或填写其他端口。

```bash
ss -ltnp | grep 810
```

### 状态为 failed

检查：

```text
data/artifacts/deployments/<deployment-id>/serve.log
```

常见原因：

- 模型路径不存在；
- 运行时缺失；
- 显存不足；
- 端口冲突。

## 17. CUDA / ROCm 未检测到

```bash
nvidia-smi
rocm-smi
curl -s http://localhost:8000/api/v1/config
```

如果只有 `cpu`：

- 驱动未安装；
- 安装的是 CPU 版 PyTorch；
- 虚拟化环境没有透传 GPU。

使用匹配的 wheel 源重新安装运行时。

## 18. 模型下载失败

使用镜像：

```bash
MODEL_SOURCE=hf-mirror MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf-mirror ./deploy.sh pull-fit
```

使用 ModelScope：

```bash
MODEL_SOURCE=ms MODEL_SET=base ./deploy.sh pull-models
FIT_SOURCE=hf FIT_BACKBONE_SOURCE=ms ./deploy.sh pull-fit
```

`vega-U` 不支持 ModelScope，Qwen reader 支持。

## 19. 数据损坏或误删

先停止服务并备份：

```bash
./deploy.sh stop
cp data/autolaya.db data/autolaya.db.bak
```

不要直接删除数据库或 `data/`，除非确认不再需要历史项目和数据。

## 20. 提交问题前

请准备：

- 操作系统、Python、Node 版本；
- `./deploy.sh status`；
- 去掉 Key 后的相关配置；
- `deploy.log` 或模型服务日志；
- 复现步骤；
- 任务 ID 和错误信息。

不要发送 API Key、真实业务数据或完整数据库。
