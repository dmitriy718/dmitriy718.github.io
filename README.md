# Agentic Uptime Maintenance Agent

Production-ready autonomous AI agent for monitoring and maintaining high-availability uptime across SaaS platforms, VPS infrastructure, and local/cloud services.

## Key Features

- **Continuous monitoring** for HTTP(S), TCP ports, systemd services, processes, logs, databases, Prometheus, Grafana, Datadog, and custom scripts.
- **Anomaly detection** using thresholds, response latency, and log pattern analysis.
- **Self-healing runbooks** with systemd restarts, Docker/Kubernetes restarts, SSH commands, and deployment triggers.
- **AI-assisted debugging** via LLM analysis of logs and code context.
- **Code introspection** for targeted patch generation and safe patch application.
- **RBAC + audit logs** for secure operations and accountability.
- **Notifications** for Slack, Email, and Telegram.
- **Webhook server** to trigger on external events.
- **Persistent memory** via SQLite for incident tracking.
- **Agentic trading engine** with market-aware risk, slippage protection, backtesting,
  explainable trade decisions, and learning loop for parameter tuning.

## Architecture

```
agentic_uptime/
  agent.py                # Core orchestration loop
  config.py               # Config models & loader
  logging_setup.py        # Logging config
  audit.py                # Audit log sink
  memory.py               # SQLite incident history
  monitoring/             # Pluggable health checks
  analysis/               # LLM + log analysis + introspection
  repair/                 # Auto-heal, deployment, patching
  notifications/          # Slack/Email/Telegram
  webhooks/               # FastAPI webhook receiver
  integrations/           # GitHub/GitLab deployments
  trading/                # Agentic trading engine
```

## Quick Start (Local)

1. **Install dependencies**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create config and env**
   ```bash
   cp config.example.yml config.yml
   cp .env.example .env
   ```

3. **Run the agent**
   ```bash
   python -m agentic_uptime.main --config config.yml
   ```

## Docker Deployment

```bash
cp config.example.yml config.yml
cp .env.example .env
docker compose up -d --build
```

## Configuration

Edit `config.yml` to define:
- **Checks** (HTTP/TCP/Systemd/Prometheus/Grafana/Datadog/Database/Log/Script/SSH)
- **Runbooks** for auto-heal steps
- **Notifications** for alerts
- **LLM provider** and model
- **RBAC roles** for allowed actions

Use `.env` to store secrets and API keys (OpenAI, Slack, GitHub, etc).

## Trading Engine

The trading engine provides:
- **Market-aware risk engine** (max position, exposure, drawdown, volatility, spread limits).
- **Slippage protection** with fallback to limit orders.
- **Strategy sandbox/backtest** with deterministic logs.
- **Self-healing execution layer** with retries and circuit breakers.
- **Explainable decisions & learning loop** with JSONL journals and adjustments.

### Trading Backtest

```bash
cp trading_config.example.yml trading_config.yml
python -m agentic_uptime.trading.main --config trading_config.yml
```

### Paper / Live

Set Binance.US credentials in `.env`:
```
BINANCE_US_API_KEY=...
BINANCE_US_API_SECRET=...
```

Then update `trading_config.yml`:
```yaml
mode: paper   # or live
exchange:
  type: binance_us
```

## Auto-Healing Flow

1. Monitor check fails repeatedly (`failure_policy.fail_after`)
2. Incident stored in SQLite
3. Diagnostics collected (logs, git status, systemctl, docker logs)
4. Log analyzer + optional LLM suggests root cause
5. Runbook executed (restart services, deploy, SSH, patch)
6. Notifications sent

## SSH Requirements

Remote operations **must use sshpass** for password-based access.
Set `SSH_PASSWORD` in `.env` and define SSH checks or runbook steps.

## Security & RBAC

- RBAC policies are enforced for privileged actions.
- Audit logs are written to `logs/audit.jsonl`.
- Every action (restart, patch, deploy, SSH) is recorded.

## Example Check Types

```yaml
checks:
  - name: public-api
    type: http
    url: https://example.com/health
    expected_status: [200]
    max_latency_ms: 500

  - name: redis-port
    type: tcp
    host: 127.0.0.1
    port: 6379
```

## Webhooks

Enable in config:
```yaml
webhooks:
  enabled: true
  host: 0.0.0.0
  port: 8080
  shared_secret_env: WEBHOOK_SECRET
```

Send a webhook:
```bash
curl -X POST http://localhost:8080/webhook \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"event":"deploy"}'
```

## Notes

- Install system packages for runtime: `sshpass`, `git`, `curl`, `openssh-client`.
- For database checks, configure correct DSN (Postgres/MySQL/SQLite).
- Prometheus and Grafana checks use their public HTTP APIs.

## Directory Tree (Generated)

```
.
├── agentic_uptime
│   ├── agent.py
│   ├── audit.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── main.py
│   ├── memory.py
│   ├── analysis
│   ├── integrations
│   ├── monitoring
│   ├── notifications
│   ├── repair
│   ├── utils
│   └── webhooks
├── config.example.yml
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── trading_config.example.yml
└── .env.example
```