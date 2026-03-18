# Cost Estimation & Hardware Requirements

Everything you need to know about running Mission Control — from a Raspberry Pi to a cloud VPS.

---

## Hardware Requirements

### Minimum (light usage, 1-2 agents)

| Resource | Spec |
|----------|------|
| CPU | 2 cores |
| RAM | 1 GB |
| Storage | 5 GB |
| Network | Outbound HTTPS |

### Recommended (all 9 agents active)

| Resource | Spec |
|----------|------|
| CPU | 4 cores |
| RAM | 2-4 GB |
| Storage | 20 GB |
| Network | Outbound HTTPS |

> **Why 20 GB storage?** The `event_log` table is append-only (audit trail), and pgvector indexes add ~2x overhead on embedding columns. 20 GB gives you years of headroom.

### What runs where

| Service | Image | RAM Usage | Notes |
|---------|-------|-----------|-------|
| PostgreSQL 16 + pgvector | `pgvector/pgvector:pg16` | 300-800 MB | Largest consumer; stores 1536-dim vectors |
| Redis 7 | `redis:7-alpine` | 50-100 MB | Session cache, minimal footprint |
| FastAPI backend | `python:3.12-slim` | 200-500 MB | Async; agents run sequentially by default |
| Next.js dashboard | `node:20-alpine` | 150-300 MB | Static build after startup |

---

## Hosting Options

| Platform | Spec | Est. Cost/mo |
|----------|------|-------------|
| **Self-hosted** (Raspberry Pi 4/5, old laptop) | 4 GB RAM, ARM or x86 | $0 (electricity only) |
| **Hetzner VPS** (CX22) | 2 vCPU, 4 GB RAM | ~$5/mo |
| **DigitalOcean Droplet** | 2 vCPU, 2 GB RAM | ~$18/mo |
| **Railway / Render** | Starter tier | ~$10-20/mo |
| **AWS Lightsail** | 2 GB instance | ~$12/mo |

All options run the full stack (database, backend, dashboard) on a single machine via Docker Compose.

---

## LLM API Costs

### Token pricing (per 1M tokens, as of March 2026)

| Model | Input | Output | Used by |
|-------|-------|--------|---------|
| **Claude Haiku 4.5** | $1.00 | $5.00 | Sage, Luna, Radar (cheap/fast agents) |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | Atlas, Forge, Scout, Echo, Pulse, Razor (smart agents) |

### Per-run cost estimates

| Agent type | Typical input | Typical output | Est. cost/run |
|------------|--------------|----------------|---------------|
| Haiku — simple (no tools) | ~2K tokens | ~500 tokens | **$0.005** |
| Haiku — with web search | ~5K tokens | ~1.5K tokens | **$0.013** |
| Sonnet — simple | ~3K tokens | ~1K tokens | **$0.024** |
| Sonnet — with web search | ~8K tokens | ~3K tokens | **$0.069** |

Every agent has a `max_budget_usd` safety cap (default $0.50, most set $0.05-$0.30) so no single run can exceed its limit.

### Default agent schedule and costs

| Agent | Model | Schedule | Runs/mo | Cost/run | Monthly |
|-------|-------|----------|---------|----------|---------|
| Conductor (daily standup) | Haiku | Daily 7:30 AM | 30 | $0.008 | $0.24 |
| Sage (daily check-in) | Haiku | Daily 8 AM | 30 | $0.005 | $0.15 |
| Luna (evening reflection) | Haiku | Daily 9 PM | 30 | $0.005 | $0.15 |
| Radar (feedback collector) | Haiku | Daily | 30 | $0.013 | $0.39 |
| Pulse (reddit scout) | Sonnet | Every 12h | 60 | $0.069 | $4.14 |
| Atlas (weekly review) | Sonnet | Sundays 10 AM | 4 | $0.024 | $0.10 |
| Razor (weekly prioritizer) | Sonnet | Weekly | 4 | $0.024 | $0.10 |
| Forge (goal decomposer) | Sonnet | On goal created | ~10 | $0.069 | $0.69 |
| Scout (idea validator) | Sonnet | On idea created | ~10 | $0.069 | $0.69 |
| Echo (content drafter) | Sonnet | On high-relevance signal | ~15 | $0.024 | $0.36 |

---

## Monthly Cost Tiers

### Tier 1 — Minimal ($0.30/mo API)

Run only the daily check-in and evening reflection agents.

| | Cost |
|--|------|
| LLM API | ~$0.30 |
| Hosting (self-hosted) | $0 |
| **Total** | **~$0.30/mo** |

### Tier 2 — Typical ($8/mo API)

All scheduled agents active, moderate manual triggers.

| | Cost |
|--|------|
| LLM API | ~$8 |
| Hosting (Hetzner CX22) | ~$5 |
| **Total** | **~$13/mo** |

### Tier 3 — Heavy ($16/mo API)

All agents active, frequent manual triggers, Telegram chat sessions.

| | Cost |
|--|------|
| LLM API | ~$16 |
| Hosting (DigitalOcean) | ~$18 |
| **Total** | **~$34/mo** |

---

## Cost Optimization Tips

| Tip | Savings |
|-----|---------|
| **Reduce Pulse frequency** — change `12h` to `24h` in `reddit-scout.yaml` | Saves ~$2/mo |
| **Disable Pulse entirely** — comment out its schedule | Saves ~$4/mo — it's ~50% of API cost |
| **Use Ollama** — set `OLLAMA_BASE_URL` for local models | $0 API cost (needs 8+ GB RAM, quality varies) |
| **Use OpenRouter** — set `OPENROUTER_API_KEY` | Access cheaper models, some free tiers |
| **Lower per-run budgets** — reduce `max_budget_usd` in skill YAML | Hard cap prevents runaway costs |

### Best-value setup

> Hetzner CX22 ($5/mo) + Anthropic API with default settings = **~$13/mo total** for a fully autonomous personal command center.

---

## Free/Self-Hosted Option

Mission Control works fully offline with Ollama:

```bash
# In .env
OLLAMA_BASE_URL=http://localhost:11434
```

| Requirement | Spec |
|-------------|------|
| RAM | 8-16 GB (for 7B-13B models) |
| GPU | Optional but recommended (NVIDIA, Apple Silicon) |
| Storage | +5-10 GB per model |
| API cost | $0 |

Trade-offs: slower inference, lower quality on complex reasoning tasks (idea validation, weekly reviews). Works great for daily check-ins and simple task management.

---

## Database Growth

| Data type | Growth rate | Notes |
|-----------|-------------|-------|
| Event log | ~50-100 MB/mo | Append-only audit trail, never auto-deleted |
| Agent runs | ~10-20 MB/mo | Stores input/output JSON per run |
| Embeddings (pgvector) | ~1-5 MB/mo | 1536-dim vectors on tasks, ideas, journal |
| Everything else | <5 MB/mo | Tasks, ideas, habits, goals, etc. |

At typical usage, expect **~100 MB/month** of database growth. A 20 GB disk gives you **15+ years** before you need to think about cleanup.

---

## Network & API Limits

| Service | Requirement |
|---------|-------------|
| Anthropic API | Outbound HTTPS to `api.anthropic.com` |
| Web search (optional) | Agents with `web_search` tool need internet access |
| Telegram bot (optional) | Outbound HTTPS for polling |
| Discord bot (optional) | Outbound WebSocket to Discord gateway |

Anthropic API rate limits depend on your plan tier. The scheduler adds 0-30s random jitter between agent runs to avoid hitting rate limits.
