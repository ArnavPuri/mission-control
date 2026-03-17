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
    Task, Idea, ReadingItem, Project, AgentConfig,
    AgentStatus, TaskStatus, EventLog,
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
    """Call the Anthropic Messages API. Returns the raw response dict.

    Supports API key auth only. OAuth tokens cannot be used with the
    Messages API directly — use the Agent SDK for OAuth-based auth.
    """
    if not settings.anthropic_api_key:
        raise ValueError(
            "Chat assistant requires ANTHROPIC_API_KEY. "
            "OAuth tokens are not supported for direct API calls."
        )

    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": settings.anthropic_api_key,
    }

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


async def call_anthropic_via_sdk(
    messages: list[dict],
    system: str,
) -> str:
    """Fallback: call via Claude Agent SDK (supports OAuth).

    This path does NOT support tool_use — it sends the full prompt as text
    and gets back a plain text response. Used when no API key is available.
    """
    from claude_agent_sdk import query, ClaudeAgentOptions

    # Flatten messages into a single prompt
    prompt_parts = []
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"] if isinstance(msg["content"], str) else json.dumps(msg["content"])
        prompt_parts.append(f"[{role}]: {content}")

    prompt = "\n\n".join(prompt_parts)

    options = ClaudeAgentOptions(
        system_prompt=system,
        model=settings.chat_model,
        max_turns=1,
    )

    full_response = ""
    async for message in query(prompt=prompt, options=options):
        if hasattr(message, "result"):
            full_response = message.result
        elif hasattr(message, "content"):
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    full_response += block.text

    return full_response


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

    Uses the Messages API with tool_use if an API key is available.
    Falls back to the Agent SDK (plain text, no tools) for OAuth auth.
    """
    # Add user message to session
    session_store.add(user_id, "user", user_message)

    # Build context
    db_context = await build_db_context(db)
    system_prompt = build_system_prompt(db_context)

    # Get conversation history
    messages = session_store.get_api_messages(user_id)

    # Choose execution path based on available auth
    if settings.anthropic_api_key:
        reply_text = await _handle_with_tools(messages, system_prompt, db)
    else:
        # OAuth path — no tool_use, just conversational
        reply_text = await call_anthropic_via_sdk(messages, system_prompt)

    # Store assistant reply in session
    session_store.add(user_id, "assistant", reply_text)

    return split_message(reply_text)


async def _handle_with_tools(
    messages: list[dict], system_prompt: str, db: AsyncSession
) -> str:
    """Handle chat with full tool_use support (requires API key)."""
    max_tool_rounds = 5

    for _ in range(max_tool_rounds):
        response = await call_anthropic(messages, system_prompt, CHAT_TOOLS)

        # Check for tool use
        tool_uses = [b for b in response.get("content", []) if b.get("type") == "tool_use"]

        if not tool_uses:
            break

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
        return "I got a bit carried away there. Could you rephrase?"

    # Extract final text response
    text_parts = [b["text"] for b in response.get("content", []) if b.get("type") == "text"]
    reply_text = "\n".join(text_parts) if text_parts else "Done."

    await db.commit()
    return reply_text
