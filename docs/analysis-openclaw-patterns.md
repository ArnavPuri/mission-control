# Open Claw Analysis — Patterns for Mission Control

_Date: 2026-03-18_

## Context

Open Claw (100k+ GitHub stars, MIT licensed) is a self-hosted personal AI
assistant with 50+ messaging integrations. This analysis identifies patterns
we can adopt to achieve our North Star: **anyone can deploy on their VPS,
customize it, and get started.**

---

## Key Patterns to Adopt

### 1. One-Command Install (P0)

**Open Claw:** `npm install -g openclaw@latest` or `docker-setup.sh` that runs
Docker Compose to build and start everything.

**Our gap:** Foundation hardening is at ~53%. No one-command install exists yet.

**Action:** Create a `setup.sh` that:
- Checks for Docker + Docker Compose
- Generates `.env` from interactive prompts (or `.env.example` defaults)
- Runs `docker compose up -d`
- Runs migrations automatically on first boot
- Prints the dashboard URL when ready

### 2. Workspace-First Configuration (P0)

**Open Claw:** Config files are the source of truth. Bootstrap files include
`SOUL.md` (agent purpose), `TOOLS.md` (capabilities), `IDENTITY.md`
(personalization), `HEARTBEAT.md` (execution schedule). All version-controllable.

**Action:** Introduce a `workspace/` directory concept:
- `workspace/config.yaml` — system settings, enabled integrations, LLM provider
- `workspace/skills/` — user skills that override bundled ones
- `workspace/identity.md` — personal context injected into all agent prompts
- Entire workspace is git-friendly, portable, and restorable

### 3. Channel Adapter Pattern (P1)

**Open Claw:** A standardized `Message` interface with per-platform adapters.
Adding a new platform = writing one adapter.

**Our gap:** Telegram, Discord, and MCP each reimplement the same tool set.

**Action:** Extract a common `Channel` interface:
```
IncomingMessage → normalize → route to handler → response → platform-specific reply
```
This makes adding Slack, WhatsApp, email trivial — just write an adapter.

### 4. Three-Tier Skill Precedence (P1)

**Open Claw:** Skills load from three locations with precedence:
1. Workspace skills (highest)
2. Managed/local skills (`~/.openclaw/skills`)
3. Bundled skills (lowest)

Override a bundled skill by creating one with the same name in a higher location.

**Action:** Implement skill loading order:
1. `workspace/skills/` (user overrides)
2. `backend/skills/` (bundled defaults)

### 5. Backup/Restore CLI (P1)

**Open Claw:** All state in `~/.openclaw/`. Backup = copy one folder.

**Action:**
- `mc backup` → dumps Postgres + workspace to a single tarball
- `mc restore <file>` → restores everything
- Document the "move to new VPS" story as a 3-step process

### 6. Sandboxed Agent Execution (P2)

**Open Claw:** Non-main sessions run in isolated Docker containers with tmpfs
mounts. Secrets stay outside the sandbox.

**Action:** For agents with `tools: [bash, write]`, run them in a sandboxed
container. Extend the existing `agent-workdir` Docker volume with per-run
isolation.

### 7. Skill Registry (P2)

**Open Claw:** ClawHub — a public skill registry with 13,700+ community skills.

**Action:** Start simple:
- GitHub repo with a `skills/` directory of contributed YAML files
- `mc install skill <name>` CLI command
- Later: web UI, ratings, one-click install

### 8. Frontend Provider Toggle (P3)

**Open Claw:** Model-agnostic design with runtime provider switching.

**Action:** Add a settings page dropdown to switch LLM providers without editing
`.env`. We already support 4 auth methods — just need the UI.

---

## What We Already Do Better

| Capability | Mission Control | Open Claw |
|-----------|----------------|-----------|
| **Database** | 24-table Postgres with pgvector, relationships, audit trail | JSONL + Markdown + SQLite FTS5 |
| **Dashboard** | Full 5-page Next.js with Kanban, heatmap, analytics | Live Canvas (newer, less mature) |
| **Cost tracking** | Per-run budgets and cost analytics built-in | Not a core feature |
| **Approval queue** | First-class human-in-the-loop with expiry | Not mentioned |
| **Structured output** | Agents must return JSON with `summary` + `actions` | Free-form |

---

## Priority Summary

| Priority | Pattern | Effort | Impact |
|----------|---------|--------|--------|
| P0 | One-command install | Medium | Unblocks everything |
| P0 | Workspace-first config | Medium | Core to deploy vision |
| P1 | Channel adapter pattern | Medium | Scalable integrations |
| P1 | Backup/restore CLI | Small | Deploy confidence |
| P1 | Three-tier skill precedence | Small | User customization |
| P2 | Sandboxed agent execution | Medium | Security for VPS |
| P2 | Skill registry | Medium | Community flywheel |
| P3 | Frontend provider toggle | Small | Polish |
