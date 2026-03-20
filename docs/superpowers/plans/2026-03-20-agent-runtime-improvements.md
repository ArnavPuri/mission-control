# Agent Runtime Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add session persistence, CLAUDE.md auto-loading, and transcript archival to the agent runtime so agents remember context across runs and conversations are auditable.

**Architecture:** Add session tracking columns to AgentConfig and a transcript column to AgentRun. The runner captures session IDs and message UUIDs from the SDK stream, resumes sessions when valid, and collects transcripts. A new run detail endpoint serves transcripts without bloating the list. The dashboard shows transcripts in expandable run details.

**Tech Stack:** Python, FastAPI, SQLAlchemy, claude-agent-sdk, Alembic, Next.js/TypeScript

**Spec:** `docs/superpowers/specs/2026-03-20-agent-runtime-improvements-design.md`

---

### Task 1: Schema Changes — Models

**Files:**
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Add session columns to AgentConfig**

After `updated_at` (around line 221), before the relationships, add:

```python
    # Session persistence
    session_id = Column(String(255), nullable=True)
    last_message_uuid = Column(String(255), nullable=True)
    session_expires_at = Column(DateTime(timezone=True), nullable=True)
    session_window_days = Column(Integer, default=7)
```

- [ ] **Step 2: Add transcript column to AgentRun**

In `AgentRun` (around line 241), after `cost_usd` and before `started_at`, add:

```python
    transcript = Column(JSON, nullable=True)  # full conversation messages, capped at 50
```

- [ ] **Step 3: Verify models import**

```bash
cd backend && source .venv/bin/activate && python -c "from app.db.models import AgentConfig, AgentRun; a = AgentConfig; print(hasattr(a, 'session_id'), hasattr(a, 'session_window_days')); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat: add session persistence + transcript columns to agent models"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `backend/app/db/migrations/versions/010_agent_sessions_and_transcripts.py`

- [ ] **Step 1: Create migration**

```python
"""Add session persistence to agent_configs and transcript to agent_runs.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"


def upgrade() -> None:
    # Session persistence on agent_configs
    op.add_column("agent_configs", sa.Column("session_id", sa.String(255), nullable=True))
    op.add_column("agent_configs", sa.Column("last_message_uuid", sa.String(255), nullable=True))
    op.add_column("agent_configs", sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_configs", sa.Column("session_window_days", sa.Integer, server_default="7", nullable=True))

    # Transcript on agent_runs
    op.add_column("agent_runs", sa.Column("transcript", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "transcript")
    op.drop_column("agent_configs", "session_window_days")
    op.drop_column("agent_configs", "session_expires_at")
    op.drop_column("agent_configs", "last_message_uuid")
    op.drop_column("agent_configs", "session_id")
```

- [ ] **Step 2: Run migration**

```bash
cd backend && source .venv/bin/activate && python -m alembic upgrade head
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/db/migrations/versions/010_agent_sessions_and_transcripts.py
git commit -m "feat: migration 010 — agent session + transcript columns"
```

---

### Task 3: CLAUDE.md Auto-Loading + Session Resume in SDK Call

**Files:**
- Modify: `backend/app/orchestrator/runner.py`

- [ ] **Step 1: Add settingSources to SDK options**

In `execute_with_agent_sdk` (around line 373), add to `options_kwargs` after `"max_turns": 10`:

```python
            "setting_sources": ["project", "user"],
```

- [ ] **Step 2: Add session resume options**

In `execute_with_agent_sdk`, after the `cli_path` block and before `options = ClaudeAgentOptions(...)`, add:

```python
        # Session resumption
        if agent.session_id and agent.session_expires_at and agent.session_expires_at > datetime.now(timezone.utc):
            options_kwargs["resume"] = agent.session_id
            if agent.last_message_uuid:
                options_kwargs["resume_session_at"] = agent.last_message_uuid
```

Note: check the SDK parameter names — it might be `resume` and `resumeSessionAt` (camelCase) or `resume_session_at` (snake_case). The SDK uses dataclass fields, so check `ClaudeAgentOptions` params. Based on the explore output, the SDK uses `resume` and `resume_session_at` as snake_case Python params.

- [ ] **Step 3: Capture session ID and messages from stream, collect transcript**

Replace the response collection loop in `execute_with_agent_sdk` with:

```python
        # Collect response, session info, and transcript
        full_response = ""
        new_session_id = None
        last_assistant_uuid = None
        transcript = []

        async for message in query(prompt=prompt, options=options):
            # Capture session ID from init message
            if hasattr(message, 'subtype') and message.subtype == 'init':
                if hasattr(message, 'session_id'):
                    new_session_id = message.session_id
                elif hasattr(message, 'data') and isinstance(message.data, dict):
                    new_session_id = message.data.get('session_id')

            # Capture result
            if hasattr(message, "result") and message.result is not None:
                full_response = message.result
                transcript.append({"role": "result", "content": str(message.result)[:2000]})

            elif hasattr(message, "content"):
                text_parts = []
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                        full_response += block.text
                if text_parts:
                    role = "assistant"
                    if hasattr(message, 'role'):
                        role = message.role
                    transcript.append({"role": role, "content": "".join(text_parts)[:2000]})

                    # Track last assistant message UUID for session resumption
                    if role == "assistant" and hasattr(message, 'uuid'):
                        last_assistant_uuid = message.uuid
                    elif role == "assistant" and hasattr(message, 'id'):
                        last_assistant_uuid = message.id

            # Cap transcript at 50 entries
            if len(transcript) > 50:
                transcript = transcript[:50]

        # Store session info and transcript on the agent for the caller to save
        self._last_session_id = new_session_id
        self._last_message_uuid = last_assistant_uuid
        self._last_transcript = transcript if transcript else None
```

- [ ] **Step 4: Initialize tracking attributes in __init__ or at class level**

At the top of the `AgentRunner` class (around line 44), add:

```python
    def __init__(self):
        self._last_session_id = None
        self._last_message_uuid = None
        self._last_transcript = None
```

If `__init__` already exists, add these lines to it.

- [ ] **Step 5: Verify import**

```bash
cd backend && source .venv/bin/activate && python -c "from app.orchestrator.runner import AgentRunner; r = AgentRunner(); print(r._last_session_id); print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/runner.py
git commit -m "feat: CLAUDE.md auto-loading + session resume + transcript capture in SDK"
```

---

### Task 4: Save Session + Transcript After Run

**Files:**
- Modify: `backend/app/orchestrator/runner.py`

- [ ] **Step 1: Save session info and transcript on success path**

In `start_run`, after the success block where `run.output_data = result` (around line 698-701), add:

```python
            # Save transcript
            run.transcript = self._last_transcript

            # Update session persistence
            if agent.session_window_days and agent.session_window_days > 0:
                if self._last_session_id:
                    agent.session_id = self._last_session_id
                if self._last_message_uuid:
                    agent.last_message_uuid = self._last_message_uuid
                agent.session_expires_at = datetime.now(timezone.utc) + timedelta(days=agent.session_window_days)
```

Make sure `timedelta` is imported (it should be already from `datetime`).

- [ ] **Step 2: Save transcript on failure path too**

In `start_run`, in the failure except block (around line 769-772), add after `run.error = str(e)`:

```python
            run.transcript = self._last_transcript
```

- [ ] **Step 3: Reset tracking state after each run**

After the `await db.flush()` (around line 796), add:

```python
        # Reset per-run state
        self._last_session_id = None
        self._last_message_uuid = None
        self._last_transcript = None
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/orchestrator/runner.py
git commit -m "feat: save session info + transcript after agent runs"
```

---

### Task 5: Run Detail API Endpoint

**Files:**
- Modify: `backend/app/api/agents.py`

- [ ] **Step 1: Exclude transcript from list endpoint**

In `list_agent_runs` (around line 340-353), the response already doesn't include `transcript` since it lists fields explicitly. No change needed — just verify `transcript` is NOT in the return dict.

- [ ] **Step 2: Add run detail endpoint**

After the `list_agent_runs` endpoint (after line 353), add:

```python
@router.get("/{agent_id}/runs/{run_id}")
async def get_agent_run(agent_id: UUID, run_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get detailed agent run including transcript."""
    run = await db.get(AgentRun, run_id)
    if not run or run.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": str(run.id),
        "agent_id": str(run.agent_id),
        "status": run.status.value,
        "trigger": run.trigger,
        "tokens_used": run.tokens_used,
        "cost_usd": run.cost_usd,
        "error": run.error,
        "output_data": run.output_data,
        "transcript": run.transcript,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
```

- [ ] **Step 3: Add session_window_days to agent detail response**

Find the `get_agent_detail` endpoint response dict and add:

```python
        "session_window_days": agent.session_window_days or 7,
```

- [ ] **Step 4: Verify import**

```bash
cd backend && source .venv/bin/activate && python -c "from app.api.agents import router; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/agents.py
git commit -m "feat: add run detail endpoint with transcript + session_window_days in agent detail"
```

---

### Task 6: API Client + Dashboard Transcript Viewer

**Files:**
- Modify: `dashboard/app/lib/api.ts`
- Modify: `dashboard/app/agents/page.tsx`

- [ ] **Step 1: Add API client method for run detail**

In `dashboard/app/lib/api.ts`, in the `agents` object (around line 156), add:

```typescript
  runDetail: (agentId: string, runId: string) => request<RunDetailResponse>(`/api/agents/${agentId}/runs/${runId}`),
```

And add the type above the agents object:

```typescript
export interface RunDetailResponse {
  id: string;
  agent_id: string;
  status: string;
  trigger: string;
  tokens_used: number;
  cost_usd: number;
  error: string | null;
  output_data: Record<string, unknown> | null;
  transcript: { role: string; content: string }[] | null;
  started_at: string;
  completed_at: string | null;
}
```

- [ ] **Step 2: Update RunDetail interface in agents page**

In `dashboard/app/agents/page.tsx`, update the `RunDetail` interface (around line 16) to include transcript:

```typescript
interface RunDetail {
  id: string;
  status: string;
  trigger: string;
  tokens_used: number;
  cost_usd: number;
  error: string | null;
  output_data: Record<string, unknown> | null;
  transcript: { role: string; content: string }[] | null;
  started_at: string;
  completed_at: string | null;
}
```

- [ ] **Step 3: Add transcript toggle to RunRow component**

In the `RunRow` component, after the duration/tokens section inside the expanded area, add:

```tsx
          {run.transcript && run.transcript.length > 0 && (
            <details className="mt-2">
              <summary className="text-[11px] text-mc-accent cursor-pointer hover:underline">
                Show transcript ({run.transcript.length} messages)
              </summary>
              <div className="mt-2 space-y-1.5 max-h-64 overflow-y-auto">
                {run.transcript.map((msg, i) => (
                  <div key={i} className={clsx(
                    'text-xs px-2.5 py-1.5 rounded',
                    msg.role === 'assistant' ? 'bg-blue-50 dark:bg-blue-950/30 text-mc-text dark:text-gray-300' :
                    msg.role === 'result' ? 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-400' :
                    'bg-gray-50 dark:bg-gray-800/50 text-mc-muted dark:text-gray-400'
                  )}>
                    <span className="font-medium text-[10px] uppercase text-mc-dim mr-1.5">{msg.role}</span>
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
```

- [ ] **Step 4: Fetch run detail (with transcript) when expanding a run**

Update the `RunRow` to lazy-load the transcript. Change the component to accept `agentId` and fetch on expand. In `AgentsPage`, when a run is expanded and `transcript` is null, fetch from the detail endpoint:

In `AgentsPage`, replace the simple `expandedRun` state with a function that fetches detail:

```typescript
  const [expandedRunData, setExpandedRunData] = useState<RunDetail | null>(null);

  const handleExpandRun = async (run: RunDetail) => {
    if (expandedRun === run.id) {
      setExpandedRun(null);
      setExpandedRunData(null);
      return;
    }
    setExpandedRun(run.id);
    if (!run.transcript && selectedAgent) {
      try {
        const detail = await api.agents.runDetail(selectedAgent, run.id);
        setExpandedRunData(detail as RunDetail);
        setDetailedRuns((prev) => prev.map((r) => r.id === run.id ? { ...r, transcript: detail.transcript } : r));
      } catch {}
    }
  };
```

Update the `RunRow` usage to call `handleExpandRun` instead of the inline toggle.

- [ ] **Step 5: TypeScript check**

```bash
cd dashboard && npx tsc --noEmit --pretty
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/app/lib/api.ts dashboard/app/agents/page.tsx
git commit -m "feat: transcript viewer in agent run details with lazy loading"
```

---

### Task 7: Agent Builder — Session Window Field

**Files:**
- Modify: `dashboard/app/agents/builder-form.tsx`

- [ ] **Step 1: Add session_window_days to FormState**

In the `FormState` interface (around line 121-138), add:

```typescript
  session_window_days: number;
```

- [ ] **Step 2: Add default value**

In the form state initialization, add `session_window_days: 7` to the defaults. If loading an existing agent, populate from the agent detail response.

- [ ] **Step 3: Add the UI field**

In the Advanced Config section (around line 696-742), add after the `chain_to` field:

```tsx
<div>
  <label className="block text-xs font-medium text-mc-muted dark:text-gray-400 mb-1">Session Memory (days)</label>
  <input
    type="number"
    min={0}
    max={30}
    value={form.session_window_days}
    onChange={(e) => setForm({ ...form, session_window_days: parseInt(e.target.value) || 0 })}
    className="w-full border border-mc-border dark:border-gray-700 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-800 text-mc-text dark:text-gray-200 outline-none focus:border-mc-accent"
  />
  <p className="text-[11px] text-mc-dim mt-1">0 = start fresh each run. Agent resumes its conversation within this window.</p>
</div>
```

- [ ] **Step 4: Include in save payload**

In the config serialization (around line 300-305), add `session_window_days` to the fields sent to the API. It should be a top-level field on the agent, not inside `config`:

```typescript
session_window_days: form.session_window_days,
```

- [ ] **Step 5: Commit**

```bash
git add dashboard/app/agents/builder-form.tsx
git commit -m "feat: add session memory (days) field to agent builder"
```

---

### Task 8: End-to-End Verification

- [ ] **Step 1: Start backend**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Trigger an agent run and verify transcript is saved**

```bash
# Run an agent
AGENT_ID=$(curl -s http://localhost:8000/api/agents | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -s -X POST http://localhost:8000/api/agents/$AGENT_ID/run | python3 -m json.tool

# Wait for completion, then check the run detail
sleep 30
RUN_ID=$(curl -s "http://localhost:8000/api/agents/$AGENT_ID/runs?limit=1" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
curl -s "http://localhost:8000/api/agents/$AGENT_ID/runs/$RUN_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print('transcript:', len(d.get('transcript') or []), 'messages')"
```

- [ ] **Step 3: Verify session was saved**

```bash
curl -s http://localhost:8000/api/agents/$AGENT_ID | python3 -c "import sys,json; d=json.load(sys.stdin); print('session_id:', d.get('session_id', 'none')[:20] if d.get('session_id') else 'none'); print('window:', d.get('session_window_days'))"
```

- [ ] **Step 4: Run the agent again and verify session resume**

```bash
# Second run should log "Resuming session..."
curl -s -X POST http://localhost:8000/api/agents/$AGENT_ID/run | python3 -m json.tool
```

Check backend logs for session resume behavior.

- [ ] **Step 5: Push**

```bash
git push origin main
```
