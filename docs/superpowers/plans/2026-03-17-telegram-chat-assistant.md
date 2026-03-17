# Telegram Chat Assistant Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Telegram bot's plain-text-as-task handler with an LLM-powered conversational assistant that can read/write Mission Control data and trigger agents.

**Architecture:** Plain text messages go to a chat handler that builds DB context, maintains a 30-min session memory, and calls the Anthropic Messages API with tool_use. The LLM can call tools (create_task, create_idea, add_reading, update_task, trigger_agent) which are executed against the DB. Session state is in-memory, keyed by Telegram user ID.

**Tech Stack:** Python, FastAPI, httpx, Anthropic Messages API (tool_use), python-telegram-bot, SQLAlchemy async

**Spec:** `docs/superpowers/specs/2026-03-17-telegram-chat-assistant-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/config.py` | Add `chat_model` and `chat_session_timeout_minutes` settings |
| `backend/app/db/context.py` | **New.** `build_db_context(db)` — queries projects, tasks, ideas, reading, agents with size limits for chat prompt |
| `backend/app/integrations/chat.py` | **New.** `ChatSession`, `SessionStore`, `call_anthropic()`, `execute_tool_call()`, `CHAT_TOOLS` — all chat-specific logic isolated from telegram.py |
| `backend/app/integrations/telegram.py` | Replace `handle_plain_text` with `handle_chat_message` that delegates to `chat.py`. Add typing indicator. |
| `backend/tests/test_db_context.py` | **New.** Tests for `build_db_context` |
| `backend/tests/test_chat.py` | **New.** Tests for session management, tool call execution, message splitting |

---

### Task 1: Add config settings

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add chat settings to Settings class**

In `backend/app/config.py`, add two fields to the `Settings` class after the existing `smart_model` field:

```python
    # --- Chat Assistant ---
    chat_model: str = "claude-sonnet-4-6"
    chat_session_timeout_minutes: int = 30
```

- [ ] **Step 2: Verify the app starts with new settings**

Run: `cd /Users/arnavpuri/development/mission-control/backend && source .venv/bin/activate && python -c "from app.config import settings; print(settings.chat_model, settings.chat_session_timeout_minutes)"`

Expected: `claude-sonnet-4-6 30`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add chat_model and chat_session_timeout_minutes config settings"
```

---

### Task 2: Build DB context function

**Files:**
- Create: `backend/app/db/context.py`
- Create: `backend/tests/test_db_context.py`

- [ ] **Step 1: Write failing test for build_db_context**

Create `backend/tests/test_db_context.py`:

```python
"""Tests for build_db_context — the shared DB context builder for chat."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.db.context import build_db_context


@pytest.mark.asyncio
async def test_build_db_context_returns_all_sections():
    """build_db_context should return dict with projects, tasks, ideas, reading, agents keys."""
    mock_db = AsyncMock()

    # Mock all query results as empty
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await build_db_context(mock_db)

    assert "projects" in result
    assert "tasks" in result
    assert "ideas" in result
    assert "reading" in result
    assert "agents" in result
    assert isinstance(result["projects"], list)
    assert isinstance(result["tasks"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/arnavpuri/development/mission-control/backend && source .venv/bin/activate && python -m pytest tests/test_db_context.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.db.context'`

- [ ] **Step 3: Implement build_db_context**

Create `backend/app/db/context.py`:

```python
"""
Shared DB context builder for the chat assistant.

Builds a JSON-serializable dict of current Mission Control state
with size limits to keep LLM prompts reasonable.
"""

import json
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Project, Task, Idea, ReadingItem, AgentConfig,
    TaskStatus, TaskPriority,
)


# Size limits for chat context
MAX_TASKS = 30
MAX_IDEAS = 15
MAX_READING = 10


async def build_db_context(db: AsyncSession) -> dict:
    """Build a complete DB context snapshot for the chat assistant.

    Returns a dict with: projects, tasks, ideas, reading, agents.
    Each section is a list of dicts, sized-limited for prompt efficiency.
    """
    context = {}

    # Projects — all (typically <10)
    result = await db.execute(select(Project).order_by(Project.name))
    context["projects"] = [
        {
            "name": p.name,
            "description": p.description[:120] if p.description else "",
            "status": p.status.value,
            "id_prefix": str(p.id)[:8],
        }
        for p in result.scalars().all()
    ]

    # Open tasks — most recent, ordered by priority
    priority_order = [TaskPriority.CRITICAL, TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]
    result = await db.execute(
        select(Task)
        .where(Task.status != TaskStatus.DONE)
        .order_by(desc(Task.created_at))
        .limit(MAX_TASKS)
    )
    tasks = result.scalars().all()
    context["tasks"] = [
        {
            "text": t.text,
            "status": t.status.value,
            "priority": t.priority.value,
            "id_prefix": str(t.id)[:8],
            "source": t.source or "manual",
        }
        for t in tasks
    ]

    # Ideas — most recent
    result = await db.execute(
        select(Idea).order_by(desc(Idea.created_at)).limit(MAX_IDEAS)
    )
    context["ideas"] = [
        {
            "text": i.text,
            "tags": i.tags or [],
            "id_prefix": str(i.id)[:8],
        }
        for i in result.scalars().all()
    ]

    # Unread reading items
    result = await db.execute(
        select(ReadingItem)
        .where(ReadingItem.is_read == False)
        .order_by(desc(ReadingItem.created_at))
        .limit(MAX_READING)
    )
    context["reading"] = [
        {
            "title": r.title,
            "url": r.url,
            "id_prefix": str(r.id)[:8],
        }
        for r in result.scalars().all()
    ]

    # Agents — all with status info
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.name))
    context["agents"] = [
        {
            "slug": a.slug,
            "description": a.description,
            "status": a.status.value if a.status else "idle",
            "schedule": f"{a.schedule_type}:{a.schedule_value}" if a.schedule_type else "manual",
        }
        for a in result.scalars().all()
    ]

    return context
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/arnavpuri/development/mission-control/backend && source .venv/bin/activate && python -m pytest tests/test_db_context.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/context.py backend/tests/test_db_context.py
git commit -m "feat: add build_db_context for chat assistant DB queries"
```

---

### Task 3: Chat module — session store and tool definitions

**Files:**
- Create: `backend/app/integrations/chat.py`
- Create: `backend/tests/test_chat.py`

- [ ] **Step 1: Write failing tests for SessionStore**

Create `backend/tests/test_chat.py`:

```python
"""Tests for the chat assistant module."""

import time
import pytest
from app.integrations.chat import SessionStore


class TestSessionStore:
    def test_add_and_get_messages(self):
        store = SessionStore(timeout_minutes=30, max_messages=20)
        store.add(user_id=123, role="user", content="hello")
        store.add(user_id=123, role="assistant", content="hi there")

        messages = store.get(user_id=123)
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_separate_users(self):
        store = SessionStore(timeout_minutes=30, max_messages=20)
        store.add(user_id=1, role="user", content="hello from user 1")
        store.add(user_id=2, role="user", content="hello from user 2")

        assert len(store.get(user_id=1)) == 1
        assert len(store.get(user_id=2)) == 1

    def test_max_messages_cap(self):
        store = SessionStore(timeout_minutes=30, max_messages=3)
        for i in range(5):
            store.add(user_id=1, role="user", content=f"msg {i}")

        messages = store.get(user_id=1)
        assert len(messages) == 3
        assert messages[0]["content"] == "msg 2"  # oldest kept

    def test_timeout_prunes_old_messages(self):
        store = SessionStore(timeout_minutes=0, max_messages=20)  # 0 min = prune everything
        store.add(user_id=1, role="user", content="old message")

        # Manually set timestamp to the past
        store._sessions[1][0]["timestamp"] = time.time() - 120

        messages = store.get(user_id=1)
        assert len(messages) == 0

    def test_empty_session_returns_empty_list(self):
        store = SessionStore(timeout_minutes=30, max_messages=20)
        assert store.get(user_id=999) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/arnavpuri/development/mission-control/backend && source .venv/bin/activate && python -m pytest tests/test_chat.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.integrations.chat'`

- [ ] **Step 3: Implement SessionStore and tool definitions**

Create `backend/app/integrations/chat.py`:

```python
"""
Chat Assistant — LLM-powered conversational handler for Telegram.

Manages session memory, builds prompts with DB context, calls the
Anthropic Messages API with tool_use, and executes actions.
"""

import json
import time
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    Task, Idea, ReadingItem, Project, AgentConfig, AgentRun,
    AgentStatus, AgentRunStatus, TaskStatus, EventLog,
)
from app.db.context import build_db_context
from app.orchestrator.runner import AgentRunner
from app.api.ws import broadcast

logger = logging.getLogger(__name__)


# --- Tool Definitions (Anthropic Messages API format) ---

CHAT_TOOLS = [
    {
        "name": "create_task",
        "description": "Create a new task in Mission Control",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Task description"},
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Task priority (default: medium)",
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name to assign to (optional, matched by name)",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "create_idea",
        "description": "Capture a new idea",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Idea description"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for the idea"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "add_reading",
        "description": "Add an item to the reading list",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the article/resource"},
                "url": {"type": "string", "description": "URL (optional)"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_task",
        "description": "Update a task's status or priority. Match tasks by text content (fuzzy match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_text": {"type": "string", "description": "Text to search for in task descriptions"},
                "status": {
                    "type": "string",
                    "enum": ["todo", "in_progress", "blocked", "done"],
                    "description": "New status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "New priority",
                },
            },
            "required": ["task_text"],
        },
    },
    {
        "name": "trigger_agent",
        "description": "Trigger a Mission Control agent to run. Check agent status first — don't start already-running agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_slug": {"type": "string", "description": "Slug of the agent to trigger"},
            },
            "required": ["agent_slug"],
        },
    },
]


# --- Session Store ---

class SessionStore:
    """In-memory session storage for chat conversations, keyed by Telegram user ID."""

    def __init__(self, timeout_minutes: int = 30, max_messages: int = 20):
        self.timeout_minutes = timeout_minutes
        self.max_messages = max_messages
        self._sessions: dict[int, list[dict]] = {}

    def add(self, user_id: int, role: str, content: str):
        """Add a message to the user's session."""
        if user_id not in self._sessions:
            self._sessions[user_id] = []

        self._sessions[user_id].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

    def get(self, user_id: int) -> list[dict]:
        """Get active session messages, pruning expired ones."""
        if user_id not in self._sessions:
            return []

        cutoff = time.time() - (self.timeout_minutes * 60)
        # Prune old messages
        self._sessions[user_id] = [
            msg for msg in self._sessions[user_id]
            if msg["timestamp"] > cutoff
        ]

        # Cap at max messages (keep most recent)
        if len(self._sessions[user_id]) > self.max_messages:
            self._sessions[user_id] = self._sessions[user_id][-self.max_messages:]

        return self._sessions[user_id]

    def get_api_messages(self, user_id: int) -> list[dict]:
        """Get messages formatted for the Anthropic Messages API."""
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.get(user_id)
        ]


# Singleton session store
session_store = SessionStore(
    timeout_minutes=settings.chat_session_timeout_minutes,
    max_messages=20,
)


# --- System Prompt ---

def build_system_prompt(db_context: dict) -> str:
    """Build the system prompt for the chat assistant."""
    return f"""You are Mission Control, a personal AI assistant.
You help manage projects, tasks, ideas, and a reading list.

## Current Data

### Projects
{json.dumps(db_context.get("projects", []), indent=2)}

### Open Tasks ({len(db_context.get("tasks", []))} shown)
{json.dumps(db_context.get("tasks", []), indent=2)}

### Recent Ideas
{json.dumps(db_context.get("ideas", []), indent=2)}

### Unread Reading List
{json.dumps(db_context.get("reading", []), indent=2)}

### Available Agents
{json.dumps(db_context.get("agents", []), indent=2)}

## Behavior
- Act immediately on clear intents and confirm what you did
- Ask for clarification on ambiguous requests
- Always confirm before destructive actions (marking tasks done, changing priorities)
- Keep replies concise — this is Telegram, not email
- When listing items, use compact formatting
- Match tasks by text content, not by ID
- Check agent status before triggering (don't start already-running agents)"""


# --- LLM Call ---

async def call_anthropic(
    messages: list[dict],
    system: str,
    tools: list[dict] | None = None,
) -> dict:
    """Call the Anthropic Messages API. Returns the raw response dict."""
    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    # Auth
    if settings.anthropic_api_key:
        headers["x-api-key"] = settings.anthropic_api_key
    elif settings.claude_code_oauth_token:
        headers["Authorization"] = f"Bearer {settings.claude_code_oauth_token}"
    else:
        raise ValueError("No Anthropic API key or OAuth token configured")

    body = {
        "model": settings.chat_model,
        "max_tokens": 2048,
        "system": system,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


# --- Tool Execution ---

async def execute_tool_call(
    name: str, input_data: dict, db: AsyncSession
) -> str:
    """Execute a single tool call and return a result string."""

    if name == "create_task":
        project_id = None
        project_name = input_data.get("project_name")
        if project_name:
            result = await db.execute(
                select(Project).where(Project.name.ilike(f"%{project_name}%"))
            )
            project = result.scalar_one_or_none()
            if project:
                project_id = project.id

        task = Task(
            text=input_data["text"],
            priority=input_data.get("priority", "medium"),
            project_id=project_id,
            source="telegram:chat",
        )
        db.add(task)
        db.add(EventLog(
            event_type="task.created",
            entity_type="task",
            source="telegram:chat",
            data={"text": task.text, "priority": task.priority},
        ))
        await db.flush()
        await broadcast("task.created", {"text": task.text, "source": "telegram:chat"})
        return f"Task created: {task.text} (priority: {task.priority})"

    elif name == "create_idea":
        idea = Idea(
            text=input_data["text"],
            tags=input_data.get("tags", []),
            source="telegram:chat",
        )
        db.add(idea)
        db.add(EventLog(
            event_type="idea.created",
            entity_type="idea",
            source="telegram:chat",
            data={"text": idea.text},
        ))
        await db.flush()
        await broadcast("idea.created", {"text": idea.text, "source": "telegram:chat"})
        return f"Idea captured: {idea.text}"

    elif name == "add_reading":
        item = ReadingItem(
            title=input_data["title"],
            url=input_data.get("url"),
            source="telegram:chat",
        )
        db.add(item)
        db.add(EventLog(
            event_type="reading.created",
            entity_type="reading",
            source="telegram:chat",
            data={"title": item.title},
        ))
        await db.flush()
        return f"Added to reading list: {item.title}"

    elif name == "update_task":
        task_text = input_data["task_text"]
        result = await db.execute(
            select(Task).where(
                Task.status != TaskStatus.DONE,
                Task.text.ilike(f"%{task_text}%"),
            )
        )
        matches = result.scalars().all()

        if not matches:
            return f"No open task found matching '{task_text}'"
        if len(matches) > 1:
            task_list = ", ".join(f'"{t.text}"' for t in matches[:5])
            return f"Multiple tasks match '{task_text}': {task_list}. Be more specific."

        task = matches[0]
        changes = []
        if "status" in input_data:
            task.status = input_data["status"]
            changes.append(f"status→{input_data['status']}")
            if input_data["status"] == "done":
                task.completed_at = datetime.now(timezone.utc)
        if "priority" in input_data:
            task.priority = input_data["priority"]
            changes.append(f"priority→{input_data['priority']}")

        db.add(EventLog(
            event_type="task.updated",
            entity_type="task",
            entity_id=task.id,
            source="telegram:chat",
            data={"changes": changes},
        ))
        await db.flush()
        return f"Updated task '{task.text}': {', '.join(changes)}"

    elif name == "trigger_agent":
        slug = input_data["agent_slug"]
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.slug == slug)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return f"Agent not found: {slug}"
        if agent.status == AgentStatus.RUNNING:
            return f"Agent {agent.name} is already running"

        runner = AgentRunner()
        try:
            run = await runner.start_run(agent, trigger="telegram:chat", db=db)
            summary = run.output_data.get("summary", "No summary") if run.output_data else "No output"
            return f"Agent {agent.name} completed: {summary[:300]}"
        except Exception as e:
            return f"Agent {agent.name} failed: {str(e)[:200]}"

    return f"Unknown tool: {name}"


# --- Message Splitting ---

TELEGRAM_MAX_LENGTH = 4096


def split_message(text: str) -> list[str]:
    """Split a message into chunks that fit Telegram's 4096 char limit."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return [text]

    chunks = []
    while text:
        if len(text) <= TELEGRAM_MAX_LENGTH:
            chunks.append(text)
            break

        # Try to split at a newline
        split_at = text.rfind("\n", 0, TELEGRAM_MAX_LENGTH)
        if split_at == -1:
            split_at = TELEGRAM_MAX_LENGTH

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


# --- Main Chat Handler ---

async def handle_chat(user_id: int, user_message: str, db: AsyncSession) -> list[str]:
    """Process a chat message and return response text(s).

    This is the main entry point called by the Telegram handler.
    Returns a list of strings (split for Telegram's message limit).
    """
    # Add user message to session
    session_store.add(user_id, "user", user_message)

    # Build context
    db_context = await build_db_context(db)
    system_prompt = build_system_prompt(db_context)

    # Get conversation history
    messages = session_store.get_api_messages(user_id)

    # Call LLM with tool loop
    max_tool_rounds = 5
    for _ in range(max_tool_rounds):
        response = await call_anthropic(messages, system_prompt, CHAT_TOOLS)

        # Check for tool use
        tool_uses = [b for b in response.get("content", []) if b.get("type") == "tool_use"]

        if not tool_uses:
            # No tool calls — extract text and return
            break

        # Process tool calls
        # Add assistant message with tool_use blocks to conversation
        messages.append({"role": "assistant", "content": response["content"]})

        # Execute each tool and build tool_result messages
        tool_results = []
        for tool_use in tool_uses:
            result_text = await execute_tool_call(tool_use["name"], tool_use["input"], db)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use["id"],
                "content": result_text,
            })

        messages.append({"role": "user", "content": tool_results})
        await db.commit()
    else:
        # Exceeded max tool rounds
        response = {"content": [{"type": "text", "text": "I got a bit carried away there. Could you rephrase?"}]}

    # Extract final text response
    text_parts = [b["text"] for b in response.get("content", []) if b.get("type") == "text"]
    reply_text = "\n".join(text_parts) if text_parts else "Done."

    # Store assistant reply in session
    session_store.add(user_id, "assistant", reply_text)

    await db.commit()

    return split_message(reply_text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/arnavpuri/development/mission-control/backend && source .venv/bin/activate && python -m pytest tests/test_chat.py -v`

Expected: PASS (5 session store tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/chat.py backend/tests/test_chat.py
git commit -m "feat: add chat module with session store, tools, and LLM integration"
```

---

### Task 4: Wire chat into Telegram handler

**Files:**
- Modify: `backend/app/integrations/telegram.py`

- [ ] **Step 1: Replace handle_plain_text with handle_chat_message**

In `backend/app/integrations/telegram.py`, replace the `handle_plain_text` function (lines 205-219) with:

```python
async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages via the LLM chat assistant."""
    if not is_allowed(update.effective_user.id):
        return
    text = update.message.text.strip()
    if not text:
        return

    # Show typing indicator while processing
    await update.message.chat.send_action("typing")

    try:
        async with async_session() as db:
            replies = await handle_chat(update.effective_user.id, text, db)

        for reply in replies:
            await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Chat handler error: {e}", exc_info=True)
        await update.message.reply_text(
            "Sorry, I couldn't process that. Try a /command instead.\n"
            f"_Error: {str(e)[:100]}_",
            parse_mode="Markdown",
        )
```

- [ ] **Step 2: Add the import for handle_chat at the top of telegram.py**

Add after the existing imports:

```python
from app.integrations.chat import handle_chat
```

- [ ] **Step 3: Update the handler registration**

In the `start_telegram_bot` function, change:

```python
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_plain_text))
```

to:

```python
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message))
```

- [ ] **Step 4: Verify the backend starts without import errors**

Run: `cd /Users/arnavpuri/development/mission-control/backend && source .venv/bin/activate && python -c "from app.integrations.telegram import handle_chat_message; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/telegram.py
git commit -m "feat: wire LLM chat assistant into Telegram plain text handler"
```

---

### Task 5: Manual integration test

**Files:** None — this is a manual verification task.

- [ ] **Step 1: Restart the backend**

Kill any running uvicorn process and restart:

```bash
cd /Users/arnavpuri/development/mission-control/backend
pkill -f "uvicorn app.main" || true
sleep 1
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
sleep 5
curl -s http://localhost:8000/health
```

Expected: `{"status":"ok","database":"connected",...}`

- [ ] **Step 2: Test via Telegram**

Send these messages to the bot and verify responses:

1. "Hey, what can you do?" → Should get a conversational reply listing capabilities
2. "What are my current projects?" → Should list Glittr and RankPilot Studio
3. "Add a task to set up Stripe webhooks for Glittr" → Should create the task and confirm
4. "What are my open tasks?" → Should list tasks including the new one
5. "/status" → Slash commands should still work as before

- [ ] **Step 3: Commit spec and plan docs**

```bash
git add docs/
git commit -m "docs: add telegram chat assistant spec and implementation plan"
```
