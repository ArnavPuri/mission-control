# Agent Builder — Design Spec

## Problem

Creating or editing agents requires writing YAML files and restarting the backend. There is no UI to create, configure, or edit agents from the dashboard. The agents API also lacks create, update, and detail endpoints.

## Goal

Add an Agent Builder page to the dashboard that lets users create agents from templates or from scratch, and edit existing agents. Back it with full CRUD API endpoints.

## Design Principles

- **No new models** — uses the existing `AgentConfig` model.
- **Templates are frontend-only** — defined as TypeScript constants, not stored in the DB.
- **Same component for create and edit** — `/agents/new` and `/agents/[id]/edit` share one form.
- **UI-created agents have `skill_file = NULL`** — distinguishes them from YAML-managed agents. The skill loader must skip agents with `skill_file = NULL` during its sync pass.
- **Soft-delete** — disabling an agent sets `status = DISABLED` instead of hard-deleting, preserving run history.

---

## API Changes

The existing agents API at `/api/agents` needs four new endpoints.

### GET /api/agents/{agent_id}

Return full agent config (all fields, not the summary returned by list).

Returns all `AgentConfig` fields including `prompt_template`, `tools`, `data_reads`, `data_writes`, `config`, `max_budget_usd`, `skill_file`, etc.

### POST /api/agents

Create a new agent from the builder form.

```python
class AgentCreate(BaseModel):
    name: str
    slug: str | None = None  # auto-generated from name if not provided
    description: str = ""
    agent_type: str = "marketing"  # marketing, research, ops, content, general
    model: str = "claude-haiku-4-5"
    max_budget_usd: float = 0.10
    prompt_template: str
    tools: list[str] = []
    schedule_type: str | None = None  # manual, interval, cron
    schedule_value: str | None = None  # "6h", "0 9 * * *"
    data_reads: list[str] = []
    data_writes: list[str] = []
    project_id: UUID | None = None
    config: dict = {}  # requires_approval, max_actions_per_run, chain_to, timeout_seconds
```

Validations:
- `name` must be unique — return 409 on conflict
- `slug` must be unique — return 409 on conflict
- If `slug` is omitted, auto-generate from name via backend slugify
- `skill_file` is always set to `NULL` for UI-created agents

Backend slugify (source of truth):
```python
import re
def slugify(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
```

Emit `EventLog` entry (`agent.created`) and WebSocket broadcast.

### PATCH /api/agents/{agent_id}

Update any subset of agent fields. Same schema as create but all fields optional. Additionally accepts:
- `status`: restricted to `idle` or `disabled` (not `running` or `error`, which are system-managed)

Validate `name` and `slug` uniqueness if either is being changed. Emit `EventLog` entry (`agent.updated`).

### DELETE /api/agents/{agent_id}

Soft-delete: sets `status = DISABLED` and returns `{"disabled": true}`. Does NOT hard-delete rows. This preserves run history, approvals, memories, and triggers.

For permanent deletion (future): would need to cascade-delete `agent_runs`, `agent_approvals`, `agent_memories`, `agent_triggers` first due to FK constraints without CASCADE.

---

## Skill Loader Update

Modify `backend/app/agents/skill_loader.py` to skip agents where `skill_file IS NULL` during its sync pass. This prevents the loader from interfering with UI-created agents.

---

## Dashboard Pages

### /agents — Existing page updates

- Add "Create Agent" button in the header (links to `/agents/new`)
- Add "Edit" button on each agent card (links to `/agents/{id}/edit`)

### /agents/new — Template Picker + Builder

**Step 1: Template Picker** (shown only on `/agents/new`, not on edit)

Grid of template cards. Ship with 3 templates for v1 (more can be added trivially later):

- **Reddit Scout** (marketing) — Find Reddit threads for product promotion
- **Daily Check-in** (productivity) — Morning task review and prioritization
- **Start from Scratch** — Empty form, configure everything manually

Each card shows: category icon, name, one-line description, model badge.

Clicking a template pre-fills the builder form and scrolls to it.

**Step 2: Builder Form**

Multi-section form on a single page:

| Section | Fields |
|---------|--------|
| **Basics** | Name (text, validates uniqueness on blur), slug (auto-generated, editable), description (textarea), agent type (select: marketing/research/ops/content/general) |
| **Prompt** | Large textarea with monospace font. Helper text showing available `{{variables}}` dynamically based on selected data reads. Frontend-only prompt preview renders variables with sample placeholders (e.g., "[3 projects]", "[5 tasks]") |
| **Model & Budget** | Model (select: claude-haiku-4-5 / claude-sonnet-4-6), max budget USD (number input), timeout seconds (number, default 300) |
| **Data Access** | Two checkbox grids side by side: "Reads from" and "Writes to". Options: projects, tasks, ideas, reading, habits, goals, journal, marketing_signals, marketing_content |
| **Tools** | Checkbox list: web_search, bash, write |
| **Schedule** | Type (select: Manual / Interval / Cron), value input shown when interval or cron selected |
| **Advanced** | Requires approval (toggle), max actions per run (number, default 5), chain to (optional agent slug select), enable/disable toggle (maps to status idle/disabled) |

**Form actions:**
- **Save** — POST (create) or PATCH (edit), then redirect to `/agents`
- **Test Run** — POST `/{id}/run?dry_run=true` (edit mode only). Shows rendered prompt preview, context sizes, tools in a result panel below the form
- **Prompt Preview** — Frontend-only preview that renders `{{variables}}` with sample data (available in both create and edit mode, no backend call needed)
- **Cancel** — Navigate back to `/agents`

### /agents/[id]/edit — Edit mode

Same component as `/agents/new`. Fetches agent config via `GET /api/agents/{id}` and pre-fills the form. No template picker shown. "Test Run" button available.

---

## Templates Definition

Templates are a TypeScript constant array. Each template is a partial agent config:

```typescript
interface AgentTemplate {
  name: string;
  description: string;
  category: 'marketing' | 'productivity';
  icon: string;  // lucide icon name
  defaults: {
    agent_type: string;
    model: string;
    max_budget_usd: number;
    prompt_template: string;
    tools: string[];
    data_reads: string[];
    data_writes: string[];
    schedule_type: string | null;
    schedule_value: string | null;
    config: Record<string, unknown>;
  };
}
```

Template prompts should be concise starter prompts. The user customizes after selection.

---

## Slug Generation

Frontend slugify (preview only):
```typescript
function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}
```

Backend slugify is the source of truth (same logic in Python). The backend re-generates the slug on save if slug is omitted.

---

## Files to Create/Modify

### New files
- `dashboard/app/agents/new/page.tsx` — Template picker + builder form (create mode)
- `dashboard/app/agents/[id]/edit/page.tsx` — Thin wrapper that loads agent and renders builder in edit mode

### Modified files
- `backend/app/api/agents.py` — Add GET detail, POST create, PATCH update, DELETE (soft) endpoints
- `backend/app/agents/skill_loader.py` — Skip agents with `skill_file = NULL` during sync
- `dashboard/app/agents/page.tsx` — Add "Create Agent" button, "Edit" button on cards
- `dashboard/app/lib/api.ts` — Add createAgent, updateAgent, deleteAgent, getAgent functions
- `backend/tests/test_api.py` — Add agent CRUD tests

---

## Out of Scope

- Agent versioning / rollback
- Prompt playground / interactive testing
- Import/export YAML from the UI
- Template marketplace / sharing
- Hard deletion with FK cascade
