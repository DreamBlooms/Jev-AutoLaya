# Deployment & API

This guide explains how to deploy a trained model locally and call it from an application.

## 1. Deploy a Model

Open Models and choose an artifact:

- Fit calibration
- Laya fine-tuned checkpoint
- GLiNER fine-tuned checkpoint

Click Deploy.

Set:

- **Host:** `127.0.0.1` by default; use `0.0.0.0` for LAN access.
- **Port:** leave blank for automatic allocation.

Status changes from `starting` to `running`.

You get an address such as:

```text
http://127.0.0.1:8100/v1/systemone
```

Deployments can be restarted, stopped, or deleted.

## 2. Health Check

```bash
curl http://127.0.0.1:8100/health
```

Laya:

```json
{"status": "ok", "model": "...", "calibrated": true}
```

GLiNER:

```json
{"status": "ok", "model": "...", "device": "cuda"}
```

## 3. Call Laya

Laya exposes:

```text
POST /v1/systemone
POST /v1/systemone/batch
GET  /health
```

### Single Request

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

Response:

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

### Batch

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

### Python

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

## 4. Call GLiNER

GLiNER exposes:

```text
POST /v1/classify
POST /v1/classify/batch
POST /v1/systemone
POST /v1/systemone/batch
GET  /health
```

### Classify

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

The result contains labels and confidence.

### Batch Classify

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

## 5. Export cURL from Playground

Playground can generate a request for you:

1. choose a model and version;
2. edit State and Schema;
3. fill in BaseURL and request model name at the bottom;
4. click “Generate cURL”;
5. copy the request.

The body uses the `/v1/systemone` shape.

## 6. Authentication

### AutoLaya Management UI

The current version has no built-in login. Do not expose `:8000` publicly.

For production:

- bind to localhost;
- expose through a reverse proxy;
- add login, TLS, and access control at the proxy.

### Laya Service

Set:

```env
LAYA_API_KEY=your_local_key
```

After restart, new deployments require:

```bash
-H 'Authorization: Bearer your_local_key'
```

GLiNER has no built-in key authentication; protect it at the network layer.

## 7. Operations

```bash
./deploy.sh start
./deploy.sh status
./deploy.sh logs
./deploy.sh restart
./deploy.sh stop
```

Main log:

```text
deploy.log
```

Model service logs:

```text
data/artifacts/deployments/<deployment-id>/serve.log
```

## 8. Backup

```bash
tar -czf autolaya-backup.tgz \
  backend/.env \
  data/autolaya.db \
  data/datasets \
  data/artifacts
```

Back up `models/` separately.

## 9. Security

- Do not commit `backend/.env`, `data/`, or `models/`.
- Do not expose the management UI publicly.
- Use a firewall, reverse proxy, and TLS for cross-host access.
- Set `LAYA_API_KEY` for Laya services.
- Back up the database and datasets regularly.

For the full endpoint list, see [API Reference](../../API.md).
