# 部署与 API

本指南说明如何把训练好的模型部署成本地服务，并在业务系统中调用。

## 1. 部署模型

打开“模型”页，在“模型产物”中选择：

- Fit 校准
- Laya 微调 checkpoint
- GLiNER 微调 checkpoint

点击“部署”。

可以设置：

- **主机**：默认 `127.0.0.1`；局域网访问可填 `0.0.0.0`；
- **端口**：留空自动分配。

部署状态会从 `starting` 变为 `running`。

部署完成后会得到一个地址，例如：

```text
http://127.0.0.1:8100/v1/systemone
```

部署列表支持：

- 重启
- 停止
- 删除

## 2. 健康检查

```bash
curl http://127.0.0.1:8100/health
```

Laya 返回：

```json
{"status": "ok", "model": "...", "calibrated": true}
```

GLiNER 返回：

```json
{"status": "ok", "model": "...", "device": "cuda"}
```

## 3. 调用 Laya

Laya 提供 Jev 兼容接口：

```text
POST /v1/systemone
POST /v1/systemone/batch
GET  /health
```

### 单条请求

```bash
curl -s http://127.0.0.1:8100/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "state": {
      "ticket": "I was charged twice this month, please refund the duplicate."
    },
    "questions": {
      "team": {
        "type": "choice",
        "instructions": "Which team should handle this ticket?",
        "criteria": {
          "billing": "Refunds, invoices, duplicate charges",
          "technical": "Bugs, outages, API errors",
          "sales": "Pricing, trials, quotes"
        }
      },
      "urgent": {
        "type": "noul",
        "instructions": "Does this need attention today?"
      }
    }
  }'
```

响应示例：

```json
{
  "model": "your-model",
  "answers": {
    "team": {
      "type": "choice",
      "choice": "billing",
      "confidence": 0.93,
      "probabilities": {
        "billing": 0.93,
        "technical": 0.05,
        "sales": 0.02
      }
    },
    "urgent": {
      "type": "noul",
      "noul": 0.12,
      "confidence": 0.88,
      "probabilities": {
        "false": 0.88,
        "true": 0.12
      }
    }
  }
}
```

### 批量请求

```bash
curl -s http://127.0.0.1:8100/v1/systemone/batch \
  -H 'Content-Type: application/json' \
  -d '{
    "states": [
      {"ticket": "Refund my duplicate charge."},
      {"ticket": "The API returns 500 after login."}
    ],
    "questions": {
      "team": {
        "type": "choice",
        "instructions": "Which team should handle this ticket?",
        "criteria": {
          "billing": "Refunds and payments",
          "technical": "Bugs and outages"
        }
      }
    }
  }'
```

### Python 调用

```python
import httpx

payload = {
    "state": {"ticket": "The API returns 500 after login."},
    "questions": {
        "team": {
            "type": "choice",
            "instructions": "Which team should handle this ticket?",
            "criteria": {
                "billing": "Refunds and payments",
                "technical": "Bugs and outages",
            },
        }
    },
}

response = httpx.post("http://127.0.0.1:8100/v1/systemone", json=payload, timeout=60)
response.raise_for_status()
print(response.json()["answers"]["team"]["choice"])
```

## 4. 调用 GLiNER

GLiNER 服务提供：

```text
POST /v1/classify
POST /v1/classify/batch
POST /v1/systemone
POST /v1/systemone/batch
GET  /health
```

### 分类

```bash
curl -s http://127.0.0.1:8102/v1/classify \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "I was charged twice this month.",
    "schema": {
      "team": {
        "labels": ["billing", "technical", "sales"],
        "prompt": "Which team should handle this ticket?"
      }
    },
    "threshold": 0.5
  }'
```

返回结果包含标签和置信度。

### 批量分类

```bash
curl -s http://127.0.0.1:8102/v1/classify/batch \
  -H 'Content-Type: application/json' \
  -d '{
    "texts": [
      "Refund my duplicate charge.",
      "The API returns 500 after login."
    ],
    "schema": {
      "team": {
        "labels": ["billing", "technical"],
        "prompt": "Which team should handle this ticket?"
      }
    },
    "batchSize": 8,
    "threshold": 0.5
  }'
```

## 5. 从 Playground 导出 cURL

Playground 可以直接生成可复制的请求：

1. 选择模型和版本；
2. 编辑 State 和 Schema；
3. 在页面底部填写 BaseURL 和请求模型名；
4. 点击“生成 cURL”；
5. 复制请求到业务系统或终端。

生成的请求体就是 `/v1/systemone` 的结构。

## 6. 鉴权

### AutoLaya 管理页面

当前版本没有内置登录鉴权。不要直接把 `:8000` 暴露到公网。

生产环境建议：

- 只监听本机；
- 通过反向代理访问；
- 在代理层增加登录、TLS 和访问控制。

### Laya 服务

可以在 `backend/.env` 设置：

```env
LAYA_API_KEY=your_local_key
```

重启后，新启动的 Laya 服务会要求：

```bash
-H 'Authorization: Bearer your_local_key'
```

GLiNER 服务目前没有内置 Key 鉴权，需要在网络层保护。

## 7. 常用运维

```bash
./deploy.sh start
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh stop
```

主服务日志：

```text
deploy.log
```

模型服务日志：

```text
data/artifacts/deployments/<deployment-id>/serve.log
```

## 8. 备份

建议备份：

```bash
tar -czf autolaya-backup.tgz \
  backend/.env \
  data/autolaya.db \
  data/datasets \
  data/artifacts
```

模型目录 `models/` 通常较大，可以单独备份。

## 9. 安全建议

- 不要提交 `backend/.env`、`data/` 或 `models/`；
- 不要公开管理页面；
- 跨机访问模型服务时使用防火墙、反向代理和 TLS；
- 设置 `LAYA_API_KEY` 保护 Laya 服务；
- 定期备份数据库和数据集。

完整的接口列表见 [API 参考](../API_ZH.md)。
