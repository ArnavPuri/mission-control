"""
Chat Assistant — LLM-powered conversational handler for Telegram.

Manages session memory, builds prompts with DB context, calls
Claude via the Agent SDK (OAuth), and executes actions.
"""

import json
import shutil
import time
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    Task, Project, Note,
    AgentStatus, TaskPriority, TaskStatus, EventLog, MarketingContent,
)
from app.orchestrator.coordinator import get_coordinator
from app.orchestrator.reminders import complete_task, set_reminder
from app.timeutil import RECURRENCES, describe, end_of_day, now_local, parse_datetime
from app.db.context import build_db_context
from app.orchestrator.runner import sdk_env, start_background_run
from app.integrations import github
from app.integrations.commands import create_dev_task, delegate, find_agent
from app.api.ws import broadcast

logger = logging.getLogger(__name__)


# --- Tool Definitions ---

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
                "due": {"type": "string", "description": "Due date, YYYY-MM-DD (optional)"},
                "remind_at": {"type": "string", "description": "When to send a reminder, YYYY-MM-DDTHH:MM local time (optional)"},
                "recurrence": {"type": "string", "enum": ["daily", "weekdays", "weekly", "monthly"]},
            },
            "required": ["text"],
        },
    },
    {
        "name": "create_note",
        "description": "Create a note for ideas, reading notes, reflections, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "content": {"type": "string", "description": "Note content (markdown)"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
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
                "due": {"type": "string", "description": "New due date, YYYY-MM-DD, or \"none\" to clear"},
                "remind_at": {"type": "string", "description": "New reminder, YYYY-MM-DDTHH:MM local time, or \"none\" to clear"},
                "recurrence": {"type": "string", "enum": ["daily", "weekdays", "weekly", "monthly", "none"]},
            },
            "required": ["task_text"],
        },
    },
    {
        "name": "trigger_agent",
        "description": "Trigger a Mission Control agent to run. Check agent status first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_slug": {"type": "string", "description": "Slug of the agent to trigger"},
            },
            "required": ["agent_slug"],
        },
    },
    {
        "name": "coordinate",
        "description": "Hand a request to the coordinator agent, which splits it across the team and answers once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "What the user wants done, with all the detail they gave"},
                "project_name": {"type": "string", "description": "Project it belongs to (optional)"},
            },
            "required": ["request"],
        },
    },
    {
        "name": "delegate_task",
        "description": "Hand a piece of work to an agent. Creates a task assigned to the agent; it works on it in the background and replies in Telegram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_slug": {"type": "string", "description": "Slug of the agent to hand it to"},
                "request": {"type": "string", "description": "What the agent should do, with all the detail the user gave"},
                "project_name": {"type": "string", "description": "Project it belongs to (optional)"},
            },
            "required": ["agent_slug", "request"],
        },
    },
    {
        "name": "create_dev_task",
        "description": "Hand coding work (a feature, bug fix, refactor) on a project to Claude Code by opening a GitHub issue in the project's repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_name": {"type": "string", "description": "Project whose repo the work is in"},
                "request": {"type": "string", "description": "What to build or fix, with all the detail the user gave"},
            },
            "required": ["project_name", "request"],
        },
    },
    {
        "name": "create_content_draft",
        "description": "Create a content draft for social media (X, LinkedIn, Instagram, YouTube, blog)",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Content title"},
                "body": {"type": "string", "description": "The content/post text"},
                "channel": {
                    "type": "string",
                    "enum": ["x", "linkedin", "instagram", "youtube", "blog"],
                    "description": "Target platform",
                },
            },
            "required": ["title", "body", "channel"],
        },
    },
]


# --- Session Store ---

class SessionStore:
    def __init__(self, timeout_minutes: int = 30, max_messages: int = 20):
        self.timeout_minutes = timeout_minutes
        self.max_messages = max_messages
        self._cache: dict[str, list[dict]] = {}

    def _key(self, user_id: int, platform: str = "telegram") -> str:
        return f"{platform}:{user_id}"

    async def load(self, user_id: int, platform: str = "telegram", db: AsyncSession | None = None):
        key = self._key(user_id, platform)
        if key in self._cache:
            return

        from app.db.models import ChatSession

        async def _do_load(session: AsyncSession):
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.user_id == str(user_id),
                    ChatSession.platform == platform,
                )
            )
            row = result.scalar_one_or_none()
            self._cache[key] = row.messages if row and row.messages else []

        if db:
            await _do_load(db)
        else:
            from app.db.session import async_session
            async with async_session() as fallback_db:
                await _do_load(fallback_db)

    async def add(self, user_id: int, role: str, content: str, platform: str = "telegram", db: AsyncSession | None = None):
        await self.load(user_id, platform, db=db)
        key = self._key(user_id, platform)

        self._cache[key].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

        self._prune(key)
        await self._save(user_id, platform, db=db)

    def _prune(self, key: str):
        cutoff = time.time() - (self.timeout_minutes * 60)
        self._cache[key] = [
            msg for msg in self._cache[key]
            if msg["timestamp"] > cutoff
        ]
        if len(self._cache[key]) > self.max_messages:
            self._cache[key] = self._cache[key][-self.max_messages:]

    async def _save(self, user_id: int, platform: str = "telegram", db: AsyncSession | None = None):
        key = self._key(user_id, platform)
        messages = self._cache.get(key, [])

        from app.db.models import ChatSession
        from datetime import datetime, timezone as tz

        async def _do_save(session: AsyncSession, should_commit: bool):
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.user_id == str(user_id),
                    ChatSession.platform == platform,
                )
            )
            chat_session = result.scalar_one_or_none()
            if chat_session:
                chat_session.messages = messages
                chat_session.last_active = datetime.now(tz.utc)
            else:
                session.add(ChatSession(
                    user_id=str(user_id),
                    platform=platform,
                    messages=messages,
                ))
            if should_commit:
                await session.commit()

        if db:
            await _do_save(db, should_commit=False)
        else:
            from app.db.session import async_session
            async with async_session() as fallback_db:
                await _do_save(fallback_db, should_commit=True)

    async def get(self, user_id: int, platform: str = "telegram", db: AsyncSession | None = None) -> list[dict]:
        await self.load(user_id, platform, db=db)
        key = self._key(user_id, platform)
        self._prune(key)
        return self._cache.get(key, [])

    async def get_api_messages(self, user_id: int, platform: str = "telegram", db: AsyncSession | None = None) -> list[dict]:
        messages = await self.get(user_id, platform, db=db)
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]


session_store = SessionStore(
    timeout_minutes=settings.chat_session_timeout_minutes,
    max_messages=20,
)


# --- System Prompt ---

def build_system_prompt(db_context: dict) -> str:
    personality = settings.bot_personality
    bot_name = personality.get("name", "MC")
    tone = personality.get("tone", "")
    style = personality.get("style", "")

    identity_section = ""
    identity = settings.identity
    if identity:
        identity_section = f"\n## About the User\n{identity}\n"

    tone_section = ""
    if tone:
        tone_section = f"\nPersonality: {tone}"
    if style:
        tone_section += f"\nStyle: {style}"

    now = now_local()
    coordinator_name = db_context.get("coordinator")
    if coordinator_name:
        delegation = (
            f"- Work for the agents (research, writing, drafting, planning, anything multi-step) goes to\n"
            f"  {coordinator_name} with coordinate: it splits the work across the team and answers once.\n"
            f"  Pass the request with all the detail the user gave. Only when the user names a specific\n"
            f"  agent (\"ask Echo to ...\") use delegate_task with that agent instead.\n"
            f"- Quick things (tasks, notes, reminders, status questions) you handle yourself, right away"
        )
    else:
        delegation = (
            "- To hand work to an agent (\"have the researcher look into X\", \"ask Echo to draft a post about Y\"),\n"
            "  use delegate_task. Pick the agent whose description fits; the agent answers in Telegram itself."
        )
    return f"""You are {bot_name}, a personal AI command center assistant.
You help manage projects, tasks, notes, agents, and content creation for social media.{tone_section}
{identity_section}
Now: {now.strftime("%A %Y-%m-%d %H:%M")} ({settings.notification_timezone})

## Current Data

### Projects
{json.dumps(db_context.get("projects", []), indent=2)}

### Open Tasks ({len(db_context.get("tasks", []))} shown)
{json.dumps(db_context.get("tasks", []), indent=2)}

### Recent Notes
{json.dumps(db_context.get("notes", []), indent=2)}

### Available Agents
{json.dumps(db_context.get("agents", []), indent=2)}

## Behavior
- Act immediately on clear intents and confirm what you did
- Ask for clarification on ambiguous requests
- Always confirm before destructive actions
- Keep replies concise — this is a chat, not an email
- When listing items, use compact formatting
- Match tasks by text content, not by ID
- You can create content drafts for X, LinkedIn, Instagram, YouTube, blog
{delegation}
- trigger_agent only runs an agent's regular scheduled job; it can't be given instructions
- Coding work on a project (features, bugs) goes to create_dev_task, not to an agent
- "Remind me ..." is a create_task with remind_at (and due set to that day). Give times as local
  YYYY-MM-DDTHH:MM, worked out from "Now" above. Repeating things ("every Monday") get a recurrence;
  completing a repeating task creates the next one

## Actions
When you need to take an action (create task, update task, create note, trigger agent, create content),
include a JSON block in your response like this:

```json
{{"reply": "Your message to the user", "actions": [{{"type": "create_task", "text": "...", "priority": "medium"}}]}}
```

Available action types:
- create_task: text (required), priority (critical/high/medium/low), project_name, due (YYYY-MM-DD),
  remind_at (YYYY-MM-DDTHH:MM), recurrence (daily/weekdays/weekly/monthly)
- update_task: task_text (required, fuzzy match), status (todo/in_progress/blocked/done), priority,
  due, remind_at, recurrence ("none" clears any of the three)
- create_note: title (required), content, tags
- trigger_agent: agent_slug (required)
- coordinate: request (required), project_name — hand the request to the coordinator
- delegate_task: agent_slug (required), request (required), project_name
- create_dev_task: project_name (required), request (required)
- create_content_draft: title (required), body (required), channel (x/linkedin/instagram/youtube/blog)

If no action is needed, just reply normally as plain text."""


# --- LLM Call (Claude Agent SDK) ---

async def call_llm(
    messages: list[dict],
    system: str,
) -> str:
    """Call Claude via the Agent SDK using OAuth token."""
    from claude_agent_sdk import query, ClaudeAgentOptions

    if not settings.claude_code_oauth_token:
        raise ValueError(
            "CLAUDE_CODE_OAUTH_TOKEN is required. "
            "Run `claude auth login` to authenticate with your Claude Code subscription."
        )

    prompt_parts = []
    for msg in messages:
        role = msg["role"].upper()
        content = msg["content"] if isinstance(msg["content"], str) else json.dumps(msg["content"])
        prompt_parts.append(f"[{role}]: {content}")

    prompt = "\n\n".join(prompt_parts)

    options_kwargs = {
        "system_prompt": system,
        "model": settings.chat_model,
        "max_turns": 1,
        # Chat answers from the context in the prompt; actions go through JSON blocks
        "tools": [],
        "env": sdk_env(),
    }
    cli_path = shutil.which("claude")
    if cli_path:
        options_kwargs["cli_path"] = cli_path

    options = ClaudeAgentOptions(**options_kwargs)

    full_response = ""
    async for message in query(prompt=prompt, options=options):
        if hasattr(message, "result"):
            full_response = message.result
        elif hasattr(message, "content"):
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    full_response += block.text

    return full_response or "Sorry, I couldn't generate a response. Please try again."


# --- Tool Execution ---

async def execute_tool_call(
    name: str, input_data: dict, db: AsyncSession
) -> str:

    if name == "create_task":
        project_id = None
        project_name = input_data.get("project_name")
        if project_name:
            result = await db.execute(
                select(Project).where(Project.name.ilike(f"%{project_name}%")).order_by(Project.name)
            )
            project = result.scalars().first()
            if project:
                project_id = project.id

        task = Task(
            text=input_data["text"],
            priority=_enum(TaskPriority, input_data.get("priority"), TaskPriority.MEDIUM),
            project_id=project_id,
            source="telegram:chat",
        )
        _apply_schedule(task, input_data)
        if task.remind_at and not task.due_date:
            task.due_date = end_of_day(task.remind_at)
        db.add(task)
        db.add(EventLog(
            event_type="task.created",
            entity_type="task",
            source="telegram:chat",
            data={"text": task.text, "priority": task.priority.value},
        ))
        await db.flush()
        await broadcast("task.created", {"text": task.text, "source": "telegram:chat"})
        when = f", reminder {describe(task.remind_at)}" if task.remind_at else ""
        return f"Task created: {task.text} (priority: {task.priority.value}{when})"

    elif name == "create_note":
        note = Note(
            title=input_data["title"],
            content=input_data.get("content", ""),
            tags=input_data.get("tags", []),
            source="telegram:chat",
        )
        db.add(note)
        await db.flush()
        await broadcast("note.created", {"title": note.title, "source": "telegram:chat"})
        return f"Note created: {note.title}"

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
        if input_data.get("status"):
            status = _enum(TaskStatus, input_data["status"], task.status)
            if status == TaskStatus.DONE:
                await complete_task(db, task, source="telegram:chat")
            else:
                task.status = status
            changes.append(f"status→{status.value}")
        if input_data.get("priority"):
            task.priority = _enum(TaskPriority, input_data["priority"], task.priority)
            changes.append(f"priority→{task.priority.value}")
        changes += _apply_schedule(task, input_data)

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
        agent, matches = await find_agent(db, slug)
        if not agent:
            return f"Agent not found: {slug}" if not matches else f"Several agents match '{slug}'"
        if agent.status == AgentStatus.DISABLED:
            return f"Agent {agent.name} is disabled"
        if not start_background_run(agent.id, trigger="telegram:chat", notify=True):
            return f"Agent {agent.name} is already running"
        return f"Started {agent.name}. I'll message you when it's done."

    elif name == "coordinate":
        lead = await get_coordinator(db)
        if not lead:
            return "No coordinator agent is set up; use delegate_task with a specific agent"
        project = None
        if input_data.get("project_name"):
            project = (await db.execute(
                select(Project).where(Project.name.ilike(f"%{input_data['project_name']}%")).order_by(Project.name)
            )).scalars().first()
        task, started = await delegate(db, lead, input_data["request"], "telegram:chat", project)
        state = "is on it" if started else "will pick it up shortly"
        return f"{lead.name} {state}: {task.text}"

    elif name == "delegate_task":
        agent, matches = await find_agent(db, input_data.get("agent_slug", ""))
        if not agent:
            return f"Agent not found: {input_data.get('agent_slug')}"
        if agent.status == AgentStatus.DISABLED:
            return f"Agent {agent.name} is disabled"
        project = None
        if input_data.get("project_name"):
            project = (await db.execute(
                select(Project).where(Project.name.ilike(f"%{input_data['project_name']}%")).order_by(Project.name)
            )).scalars().first()
        task, started = await delegate(db, agent, input_data["request"], "telegram:chat", project)
        state = "is on it" if started else "is busy; it's queued"
        return f"{agent.name} {state}: {task.text}"

    elif name == "create_dev_task":
        project = (await db.execute(
            select(Project).where(Project.name.ilike(f"%{input_data.get('project_name', '')}%")).order_by(Project.name)
        )).scalars().first()
        if not project:
            return f"Project not found: {input_data.get('project_name')}"
        try:
            task, url = await create_dev_task(db, project, input_data["request"], "telegram:chat")
        except github.GitHubError as e:
            return f"Couldn't open the GitHub issue: {e}"
        return f"Opened {url} for Claude Code"

    elif name == "create_content_draft":
        content = MarketingContent(
            title=input_data["title"],
            body=input_data["body"],
            channel=input_data["channel"],
            source="telegram:chat",
        )
        db.add(content)
        await db.flush()
        return f"Content draft created for {input_data['channel']}: {input_data['title']}"

    return f"Unknown tool: {name}"


def _enum(enum_cls, value, default):
    try:
        return enum_cls(str(value).lower()) if value else default
    except ValueError:
        return default


def _apply_schedule(task: Task, data: dict) -> list[str]:
    """Apply due / remind_at / recurrence from a chat action. Returns what changed."""
    changes = []
    if data.get("due"):
        value = str(data["due"]).strip()
        due = None if value.lower() == "none" else parse_datetime(value)
        if due and len(value) == 10:  # a date: due by the end of that day
            due = end_of_day(due)
        if due or value.lower() == "none":
            task.due_date = due
            changes.append(f"due→{describe(due) if due else 'none'}")
    if data.get("remind_at"):
        value = str(data["remind_at"]).strip()
        when = None if value.lower() == "none" else parse_datetime(value)
        if when or value.lower() == "none":
            set_reminder(task, when)
            changes.append(f"reminder→{describe(when) if when else 'none'}")
    if data.get("recurrence"):
        value = str(data["recurrence"]).lower()
        if value in RECURRENCES or value == "none":
            task.recurrence = None if value == "none" else value
            changes.append(f"repeats→{value}")
    return changes


# --- Message Splitting ---

TELEGRAM_MAX_LENGTH = 4096


def split_message(text: str) -> list[str]:
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return [text]

    chunks = []
    while text:
        if len(text) <= TELEGRAM_MAX_LENGTH:
            chunks.append(text)
            break

        split_at = text.rfind("\n", 0, TELEGRAM_MAX_LENGTH)
        if split_at == -1:
            split_at = TELEGRAM_MAX_LENGTH

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


# --- Main Chat Handler ---

async def handle_chat(user_id: int, user_message: str, db: AsyncSession) -> list[str]:
    await session_store.add(user_id, "user", user_message, db=db)

    db_context = await build_db_context(db)
    lead = await get_coordinator(db)
    if lead:
        db_context["coordinator"] = lead.name
    system_prompt = build_system_prompt(db_context)
    messages = await session_store.get_api_messages(user_id, db=db)

    reply_text = await call_llm(messages, system_prompt)

    # Check if the LLM embedded action blocks in the response
    actions, clean_reply = _extract_actions(reply_text)
    if actions:
        action_results = []
        for action in actions:
            result = await execute_tool_call(action["name"], action.get("input", {}), db)
            action_results.append(result)
        await db.commit()
        if clean_reply:
            reply_text = clean_reply
        else:
            reply_text = "\n".join(action_results)

    await session_store.add(user_id, "assistant", reply_text, db=db)
    return split_message(reply_text)


def _extract_actions(text: str) -> tuple[list[dict], str]:
    """Extract JSON action blocks from LLM response if present.

    Looks for ```json blocks containing action arrays, or a top-level
    JSON object with "actions" key.
    """
    import re

    # Try to find ```json blocks with actions
    pattern = r'```json\s*(\{[^`]*"actions"\s*:\s*\[[^`]*\})\s*```'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            actions = data.get("actions", [])
            clean = text[:match.start()].strip() + text[match.end():].strip()
            # Convert to tool call format
            tool_calls = []
            for a in actions:
                if isinstance(a, dict) and "type" in a:
                    name = a.pop("type")
                    tool_calls.append({"name": name, "input": a})
            return tool_calls, clean
        except (json.JSONDecodeError, KeyError):
            pass

    # Try parsing entire response as JSON (for structured responses)
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            data = json.loads(stripped)
            if "actions" in data and isinstance(data["actions"], list):
                tool_calls = []
                for a in data["actions"]:
                    if isinstance(a, dict) and "type" in a:
                        name = a.pop("type")
                        tool_calls.append({"name": name, "input": a})
                return tool_calls, data.get("reply", data.get("summary", ""))
        except json.JSONDecodeError:
            pass

    return [], text
