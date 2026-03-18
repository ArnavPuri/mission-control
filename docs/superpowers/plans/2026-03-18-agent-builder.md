# Agent Builder Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Agent Builder page with full CRUD API, template picker, and multi-section form for creating and editing agents from the dashboard.

**Architecture:** Backend adds 4 endpoints to the existing agents router (GET detail, POST create, PATCH update, DELETE soft-delete). Frontend adds a builder page at `/agents/new` with a shared form component reused at `/agents/[id]/edit`. Skill loader updated to skip UI-created agents.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Next.js/React, Tailwind CSS, Radix UI, Lucide icons

**Spec:** `docs/superpowers/specs/2026-03-18-agent-builder-design.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `dashboard/app/agents/new/page.tsx` | Template picker + builder form (create mode) |
| `dashboard/app/agents/[id]/edit/page.tsx` | Thin wrapper, loads agent, renders builder in edit mode |

### Modified files
| File | Changes |
|------|---------|
| `backend/app/api/agents.py` | Add GET detail, POST create, PATCH update, DELETE (soft) endpoints + Pydantic schemas |
| `backend/app/agents/skill_loader.py` | Skip agents with `skill_file IS NULL` during sync |
| `dashboard/app/agents/page.tsx` | Add "Create Agent" button + "Edit" link on agent cards |
| `dashboard/app/lib/api.ts` | Add `get`, `create`, `update`, `delete` to `agents` namespace + `AgentDetail` interface |
| `backend/tests/test_api.py` | Add agent CRUD tests |

---

### Task 1: Backend Agent CRUD API + Tests

**Files:**
- Modify: `backend/app/api/agents.py`
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Write tests for agent CRUD**

Add to `backend/tests/test_api.py`:

```python
# --- Agent CRUD ---

@pytest.mark.asyncio
async def test_create_agent(client):
    resp = await client.post("/api/agents", json={
        "name": "Test Agent",
        "description": "A test agent",
        "agent_type": "marketing",
        "model": "claude-haiku-4-5",
        "prompt_template": "You are a test agent. {{projects}}",
        "tools": ["web_search"],
        "data_reads": ["projects"],
        "data_writes": ["tasks"],
        "max_budget_usd": 0.15,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Agent"
    assert data["slug"] == "test-agent"
    assert data["skill_file"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_create_agent_duplicate_name(client):
    await client.post("/api/agents", json={
        "name": "Unique Agent", "agent_type": "ops",
        "prompt_template": "test", "model": "claude-haiku-4-5",
    })
    resp = await client.post("/api/agents", json={
        "name": "Unique Agent", "agent_type": "ops",
        "prompt_template": "test2", "model": "claude-haiku-4-5",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_agent_detail(client):
    create = await client.post("/api/agents", json={
        "name": "Detail Agent", "agent_type": "research",
        "prompt_template": "Hello {{tasks}}", "model": "claude-haiku-4-5",
        "data_reads": ["tasks"], "tools": ["web_search"],
    })
    agent_id = create.json()["id"]
    resp = await client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt_template"] == "Hello {{tasks}}"
    assert data["tools"] == ["web_search"]
    assert data["data_reads"] == ["tasks"]


@pytest.mark.asyncio
async def test_update_agent(client):
    create = await client.post("/api/agents", json={
        "name": "Update Me", "agent_type": "ops",
        "prompt_template": "original", "model": "claude-haiku-4-5",
    })
    agent_id = create.json()["id"]
    resp = await client.patch(f"/api/agents/{agent_id}", json={
        "description": "Updated desc",
        "model": "claude-sonnet-4-6",
    })
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated desc"
    assert resp.json()["model"] == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_delete_agent_soft(client):
    create = await client.post("/api/agents", json={
        "name": "Delete Me", "agent_type": "ops",
        "prompt_template": "test", "model": "claude-haiku-4-5",
    })
    agent_id = create.json()["id"]
    resp = await client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["disabled"] == True
    # Agent still exists but is disabled
    detail = await client.get(f"/api/agents/{agent_id}")
    assert detail.json()["status"] == "disabled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -k "agent" -v`
Expected: FAIL (endpoints don't exist yet)

- [ ] **Step 3: Add CRUD endpoints to agents.py**

Add to `backend/app/api/agents.py` — keep all existing endpoints, add these new ones:

```python
import re
from app.db.models import EventLog
from app.api.ws import broadcast


def _slugify(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _serialize_full(a: AgentConfig) -> dict:
    return {
        "id": str(a.id),
        "name": a.name,
        "slug": a.slug,
        "description": a.description,
        "agent_type": a.agent_type,
        "status": a.status.value,
        "model": a.model,
        "max_budget_usd": a.max_budget_usd,
        "prompt_template": a.prompt_template,
        "tools": a.tools or [],
        "schedule_type": a.schedule_type,
        "schedule_value": a.schedule_value,
        "data_reads": a.data_reads or [],
        "data_writes": a.data_writes or [],
        "project_id": str(a.project_id) if a.project_id else None,
        "config": a.config or {},
        "skill_file": a.skill_file,
        "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


class AgentCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str = ""
    agent_type: str = "marketing"
    model: str = "claude-haiku-4-5"
    max_budget_usd: float = 0.10
    prompt_template: str
    tools: list[str] = []
    schedule_type: str | None = None
    schedule_value: str | None = None
    data_reads: list[str] = []
    data_writes: list[str] = []
    project_id: str | None = None
    config: dict = {}


class AgentUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    agent_type: str | None = None
    model: str | None = None
    max_budget_usd: float | None = None
    prompt_template: str | None = None
    tools: list[str] | None = None
    schedule_type: str | None = None
    schedule_value: str | None = None
    data_reads: list[str] | None = None
    data_writes: list[str] | None = None
    project_id: str | None = None
    config: dict | None = None
    status: str | None = None  # only idle or disabled


# IMPORTANT: Place this BEFORE the /{agent_id}/run route to avoid path conflicts
@router.get("/{agent_id}")
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _serialize_full(agent)


@router.post("")
async def create_agent(data: AgentCreate, db: AsyncSession = Depends(get_db)):
    slug = data.slug or _slugify(data.name)

    # Check name uniqueness
    existing_name = await db.execute(select(AgentConfig).where(AgentConfig.name == data.name))
    if existing_name.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent name already exists")

    # Check slug uniqueness
    existing_slug = await db.execute(select(AgentConfig).where(AgentConfig.slug == slug))
    if existing_slug.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent slug already exists")

    agent = AgentConfig(
        name=data.name,
        slug=slug,
        description=data.description,
        agent_type=data.agent_type,
        model=data.model,
        max_budget_usd=data.max_budget_usd,
        prompt_template=data.prompt_template,
        tools=data.tools,
        schedule_type=data.schedule_type,
        schedule_value=data.schedule_value,
        data_reads=data.data_reads,
        data_writes=data.data_writes,
        project_id=UUID(data.project_id) if data.project_id else None,
        config=data.config,
        skill_file=None,  # UI-created agents have no skill file
    )
    db.add(agent)
    await db.flush()
    db.add(EventLog(
        event_type="agent.created", entity_type="agent",
        entity_id=agent.id, source="dashboard",
        data={"name": agent.name, "agent_type": agent.agent_type},
    ))
    await broadcast("agent.created", {"id": str(agent.id), "name": agent.name})
    return _serialize_full(agent)


@router.patch("/{agent_id}")
async def update_agent(agent_id: UUID, data: AgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    updates = data.model_dump(exclude_unset=True)

    # Validate name uniqueness if changing
    if "name" in updates and updates["name"] != agent.name:
        existing = await db.execute(select(AgentConfig).where(AgentConfig.name == updates["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Agent name already exists")

    # Validate slug uniqueness if changing
    if "slug" in updates and updates["slug"] != agent.slug:
        existing = await db.execute(select(AgentConfig).where(AgentConfig.slug == updates["slug"]))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Agent slug already exists")

    # Restrict status changes to idle/disabled
    if "status" in updates:
        if updates["status"] not in ("idle", "disabled"):
            raise HTTPException(status_code=400, detail="Status can only be set to idle or disabled")
        updates["status"] = AgentStatus(updates["status"])

    if "project_id" in updates:
        updates["project_id"] = UUID(updates["project_id"]) if updates["project_id"] else None

    for key, val in updates.items():
        setattr(agent, key, val)
    await db.flush()
    return _serialize_full(agent)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.status = AgentStatus.DISABLED
    await db.flush()
    return {"disabled": True}
```

**IMPORTANT route ordering:** The `GET /{agent_id}` detail endpoint must be placed BEFORE the `POST /{agent_id}/run` and `POST /{agent_id}/stop` routes in the file. Otherwise FastAPI will try to match "run" or "stop" as a UUID and fail. The recommended order in the file is:
1. `GET ""` (list)
2. `POST ""` (create)
3. `GET "/{agent_id}"` (detail)
4. `PATCH "/{agent_id}"` (update)
5. `DELETE "/{agent_id}"` (delete)
6. `POST "/{agent_id}/run"` (run)
7. `POST "/{agent_id}/stop"` (stop)
8. `GET "/{agent_id}/runs"` (list runs)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -k "agent" -v`
Expected: All 5 agent tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/agents.py backend/tests/test_api.py
git commit -m "feat(agent-builder): add agent CRUD API with tests"
```

---

### Task 2: Skill Loader Update

**Files:**
- Modify: `backend/app/agents/skill_loader.py`

- [ ] **Step 1: Update skill_loader.py to skip UI-created agents**

The skill loader's docstring says it "disables agents whose skill files were removed" but this logic isn't implemented yet. To future-proof, add a filter. After the `for path in skill_files` loop (after line 104), before `await db.commit()`, add nothing — but update the `slugify` function to match the backend's canonical slugify:

```python
import re

def slugify(name: str) -> str:
    """Convert agent name to filesystem-safe slug."""
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
```

And add a comment after line 104 making the UI-agent safety explicit:

```python
        # Note: Only YAML-managed agents (skill_file IS NOT NULL) are synced.
        # Agents created via the UI (skill_file = NULL) are never touched by the loader.
        await db.commit()
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && python3 -c "from app.agents.skill_loader import sync_skills_to_db; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/skill_loader.py
git commit -m "feat(agent-builder): update skill loader slugify and add UI-agent safety note"
```

---

### Task 3: API Client Functions

**Files:**
- Modify: `dashboard/app/lib/api.ts`

- [ ] **Step 1: Extend Agent interface and agents namespace**

In `dashboard/app/lib/api.ts`, update the `Agent` interface (around line 116) to add the full detail fields. Then extend the `agents` namespace (around line 131) with new methods.

Add a new interface after `Agent`:

```typescript
export interface AgentDetail extends Agent {
  max_budget_usd: number;
  prompt_template: string;
  tools: string[];
  data_reads: string[];
  data_writes: string[];
  config: Record<string, unknown>;
  skill_file: string | null;
  created_at: string;
  updated_at: string | null;
}
```

Extend the `agents` namespace to add `get`, `create`, `update`, `delete`, `dryRun`:

```typescript
export const agents = {
  list: () => request<Agent[]>('/api/agents'),
  get: (id: string) => request<AgentDetail>(`/api/agents/${id}`),
  create: (data: Partial<AgentDetail>) => request<AgentDetail>('/api/agents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AgentDetail>) => request<AgentDetail>(`/api/agents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: string) => request<{ disabled: boolean }>(`/api/agents/${id}`, { method: 'DELETE' }),
  run: (id: string) => request<{ run_id: string; status: string }>(`/api/agents/${id}/run`, { method: 'POST' }),
  dryRun: (id: string) => request<Record<string, unknown>>(`/api/agents/${id}/run?dry_run=true`, { method: 'POST' }),
  stop: (id: string) => request<{ status: string }>(`/api/agents/${id}/stop`, { method: 'POST' }),
  runs: (id: string, limit = 20) => request<AgentRun[]>(`/api/agents/${id}/runs?limit=${limit}`),
};
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/lib/api.ts
git commit -m "feat(agent-builder): add agent CRUD and detail to API client"
```

---

### Task 4: Agents Page — Create & Edit Buttons

**Files:**
- Modify: `dashboard/app/agents/page.tsx`

- [ ] **Step 1: Add Create Agent button and Edit links**

Read `dashboard/app/agents/page.tsx` fully. Then:

1. Add `Plus, Pencil` to the lucide-react import
2. Add `Link` import from `next/link`
3. Add a "Create Agent" button in the page header (top-right) that links to `/agents/new`:
```tsx
<Link href="/agents/new" className="flex items-center gap-1.5 px-3 py-1.5 bg-mc-accent text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
  <Plus size={14} /> Create Agent
</Link>
```
4. Add an "Edit" button on each agent card that links to `/agents/${a.id}/edit`:
```tsx
<Link href={`/agents/${a.id}/edit`} className="text-mc-muted hover:text-mc-text transition-colors">
  <Pencil size={14} />
</Link>
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/agents/page.tsx
git commit -m "feat(agent-builder): add Create Agent button and Edit links to agents page"
```

---

### Task 5: Agent Builder Page (Create Mode)

**Files:**
- Create: `dashboard/app/agents/new/page.tsx`

- [ ] **Step 1: Create the builder page**

Create `dashboard/app/agents/new/page.tsx` with:

**Template Picker Section:**
- Grid of 3 template cards: Reddit Scout (marketing), Daily Check-in (productivity), Start from Scratch
- Each card: icon, name, description, model badge
- Clicking pre-fills the form below and scrolls to it
- Has a state `showForm` that becomes true after template selection

**Builder Form Sections:**
1. **Basics** — Name (text input, onChange generates slug preview), slug (text input, editable), description (textarea), agent_type (select: marketing/research/ops/content/general)
2. **Prompt** — Large monospace textarea. Below it, a helper showing available `{{variables}}` based on checked data_reads (e.g., if "projects" is checked, show `{{projects}}`). A "Preview" button that renders the prompt with placeholder text in a collapsible panel.
3. **Model & Budget** — Model select (claude-haiku-4-5 / claude-sonnet-4-6), max_budget_usd (number), timeout_seconds in config (number, default 300)
4. **Data Access** — Two side-by-side checkbox grids: "Reads from" and "Writes to". Options: projects, tasks, ideas, reading, habits, goals, journal, marketing_signals, marketing_content
5. **Tools** — Checkboxes: web_search, bash, write
6. **Schedule** — Type select (Manual/Interval/Cron). When interval: text input for value (e.g., "6h"). When cron: text input for cron expression.
7. **Advanced** — requires_approval toggle, max_actions_per_run number input, chain_to text input

**Form actions:**
- "Save Agent" button — calls `agents.create()`, redirects to `/agents` on success, shows error toast on failure
- "Cancel" — navigates back to `/agents`

**Template definitions** (TypeScript constants in the file):

```typescript
const TEMPLATES: AgentTemplate[] = [
  {
    name: 'Reddit Scout',
    description: 'Find Reddit threads for product promotion',
    category: 'marketing',
    icon: 'Radio',
    defaults: {
      agent_type: 'marketing',
      model: 'claude-sonnet-4-6',
      max_budget_usd: 0.25,
      prompt_template: `You are a Reddit marketing scout. Find Reddit threads where the following products could be naturally mentioned.\n\nPROJECTS:\n{{projects}}\n\nSearch for recent, relevant threads. For each opportunity, create a signal with the thread details and optionally draft a helpful reply.\n\nRespond with JSON:\n{\n  "summary": "Found N opportunities",\n  "actions": [\n    {"type": "create_signal", "title": "...", "body": "...", "source_type": "reddit", "source_url": "...", "relevance_score": 0.8, "signal_type": "opportunity"}\n  ]\n}`,
      tools: ['web_search'],
      data_reads: ['projects', 'tasks'],
      data_writes: ['marketing_signals', 'marketing_content'],
      schedule_type: 'interval',
      schedule_value: '6h',
      config: { max_actions_per_run: 10 },
    },
  },
  {
    name: 'Daily Check-in',
    description: 'Morning task review and prioritization',
    category: 'productivity',
    icon: 'Sun',
    defaults: {
      agent_type: 'ops',
      model: 'claude-haiku-4-5',
      max_budget_usd: 0.10,
      prompt_template: `You are a daily check-in assistant. Review today's tasks, habits, and goals to help prioritize the day.\n\nTASKS:\n{{tasks}}\n\nHABITS:\n{{habits}}\n\nGOALS:\n{{goals}}\n\nProvide a prioritized plan and any suggestions.\n\nRespond with JSON:\n{\n  "summary": "Today's priorities: ...",\n  "actions": []\n}`,
      tools: [],
      data_reads: ['tasks', 'habits', 'goals'],
      data_writes: [],
      schedule_type: 'cron',
      schedule_value: '0 9 * * *',
      config: {},
    },
  },
];
```

**Patterns to follow:**
- Read `dashboard/app/agents/page.tsx` and `dashboard/app/marketing/page.tsx` for component patterns
- Use shared components: `Card`, `Badge`, `SectionHeader` from `../components/shared`
- Use `'use client'` directive
- Dark mode via `dark:` Tailwind classes
- `useRouter()` from `next/navigation` for redirects
- Mobile responsive (form sections stack vertically)

- [ ] **Step 2: Verify page loads**

Navigate to `http://localhost:3000/agents/new`
Expected: Template picker shows, form works

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/agents/new/page.tsx
git commit -m "feat(agent-builder): add agent builder page with template picker"
```

---

### Task 6: Agent Edit Page

**Files:**
- Create: `dashboard/app/agents/[id]/edit/page.tsx`

- [ ] **Step 1: Create the edit page wrapper**

Create `dashboard/app/agents/[id]/edit/page.tsx` — a thin wrapper that:

1. Reads `id` from the route params
2. Fetches the agent via `agents.get(id)`
3. Renders the same builder form as `/agents/new` but pre-filled with agent data
4. No template picker shown
5. Adds a "Test Run" button that calls `agents.dryRun(id)` and shows the result in a collapsible panel below the form
6. Save calls `agents.update(id, data)` instead of `agents.create(data)`

**Implementation approach:** Extract the builder form into a shared component within the `new/page.tsx` file (exported as a named export), then import it in the edit page. Or, simpler: make the `new/page.tsx` accept an optional `agentId` search param and handle both modes. The recommended approach is to extract a `<AgentBuilderForm>` component.

The simplest approach: have `[id]/edit/page.tsx` fetch the agent, then render the form component imported from the `new` page module.

- [ ] **Step 2: Verify edit page loads**

Navigate to an agent's edit page by clicking "Edit" on the agents page.
Expected: Form pre-filled with agent config, save works.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/agents/[id]/edit/page.tsx dashboard/app/agents/new/page.tsx
git commit -m "feat(agent-builder): add agent edit page"
```

---

### Task 7: Run Full Test Suite

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -v`
Expected: All tests pass (existing + 5 new agent CRUD tests)

- [ ] **Step 2: Fix any failures**

- [ ] **Step 3: Final commit if needed**

```bash
git add -A && git commit -m "fix: resolve test failures from agent builder integration"
```
