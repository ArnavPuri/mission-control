"""
Chat Assistant — LLM-powered conversational handler for Telegram.

Manages session memory, builds prompts with DB context, calls
Claude via the Agent SDK (OAuth), and executes actions.
"""

import json
import os
import shutil
import time
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    Task, Project, AgentConfig, Note,
    AgentStatus, TaskStatus, EventLog, MarketingContent,
)
from app.db.context import build_db_context
from app.orchestrator.runner import AgentRunner
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

    return f"""You are {bot_name}, a personal AI command center assistant.
You help manage projects, tasks, notes, agents, and content creation for social media.{tone_section}
{identity_section}
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
- You can spawn agents for research, coding, marketing tasks

## Actions
When you need to take an action (create task, update task, create note, trigger agent, create content),
include a JSON block in your response like this:

```json
{{"reply": "Your message to the user", "actions": [{{"type": "create_task", "text": "...", "priority": "medium"}}]}}
```

Available action types:
- create_task: text (required), priority (critical/high/medium/low), project_name
- update_task: task_text (required, fuzzy match), status (todo/in_progress/blocked/done), priority
- create_note: title (required), content, tags
- trigger_agent: agent_slug (required)
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

    env = dict(os.environ)
    env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token

    options_kwargs = {
        "system_prompt": system,
        "model": settings.chat_model,
        "max_turns": 1,
        "env": env,
    }
    cli_path = shutil.which("claude")
    if cli_path:
        options_kwargs["cli_path"] = cli_path

    options = ClaudeAgentOptions(**options_kwargs)

    full_response = ""
    try:
        async for message in query(prompt=prompt, options=options):
            msg_type = type(message).__name__
            if hasattr(message, "result"):
                print(f"[chat-sdk] {msg_type} result={repr(message.result)[:200]}", flush=True)
                if message.result:
                    full_response = message.result
            elif hasattr(message, "content"):
                content = getattr(message, "content", [])
                texts = []
                if isinstance(content, list):
                    for block in content:
                        if hasattr(block, "text"):
                            texts.append(block.text)
                elif isinstance(content, str):
                    texts.append(content)
                if texts:
                    joined = "".join(texts)
                    full_response += joined
                    print(f"[chat-sdk] {msg_type} text={joined[:200]}", flush=True)
                else:
                    print(f"[chat-sdk] {msg_type} content_type={type(content).__name__} content={repr(content)[:200]}", flush=True)
    except Exception as e:
        print(f"[chat-sdk] ERROR: {e}", flush=True)
        logger.error(f"Chat SDK call failed: {e}", exc_info=True)
        return None

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
