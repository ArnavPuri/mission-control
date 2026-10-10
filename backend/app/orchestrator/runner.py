"""
Agent Runner - Executes agents using the Claude Agent SDK.

Uses Claude Code subscription (OAuth) exclusively.
"""

import asyncio
import json
import os
import logging
import random
import shutil
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    AgentConfig, AgentRun, AgentStatus, AgentRunStatus,
    Project, Task, EventLog, TaskStatus, TaskPriority,
    AgentApproval, AgentMemory, Note, MarketingContent, TaskComment, LEAD_TAG,
)
from app.orchestrator import review, threads
from app.db.session import async_session
from app.api.brand import get_notification_prefs_dict
from app.api.ws import broadcast
from app.api.notifications import create_notification
from app.orchestrator.schemas import validate_agent_output

logger = logging.getLogger(__name__)


class AgentRunner:
    """Executes agent runs against the Claude Agent SDK."""

    def __init__(self):
        self._last_transcript = None
        self._last_cost_usd = 0.0
        self._last_tokens = 0

    def _build_system_prompt(self, agent: AgentConfig) -> str:
        persona = (agent.config or {}).get("persona", "")
        tone = (agent.config or {}).get("tone", "")

        parts = []

        if persona:
            parts.append(f"You are {agent.name} — {persona}.")
        else:
            parts.append(f"You are {agent.name}, a specialized AI agent.")

        if agent.description:
            parts.append(f"Role: {agent.description}")

        if tone:
            parts.append(f"Tone: {tone}.")

        identity = settings.identity
        if identity:
            parts.append(f"\n## About the User\n{identity}")

        parts.append(
            "\n## Memory\n"
            "You have persistent memory that survives between runs.\n"
            '- Your context includes "past_runs" showing your last 5 runs.\n'
            '- Your "memory" dict contains things you saved previously.\n'
            '- To remember something, include a save_memory action with "key" and "value".\n'
            "- Avoid repeating the same actions from recent runs."
        )

        parts.append(
            "\n## Output Format\n"
            "You MUST respond with valid JSON only. No markdown, no explanation.\n"
            'Your output should contain a "summary" string and an "actions" array.'
        )

        return "\n".join(parts)

    async def build_context(self, agent: AgentConfig, db: AsyncSession) -> dict:
        context = {}

        if "projects" in (agent.data_reads or []):
            result = await db.execute(select(Project))
            context["projects"] = [
                {"id": str(p.id), "name": p.name, "description": p.description, "status": p.status.value}
                for p in result.scalars().all()
            ]

        if "tasks" in (agent.data_reads or []):
            query = select(Task).where(Task.status != TaskStatus.DONE)
            if agent.project_id:
                query = query.where(Task.project_id == agent.project_id)
            result = await db.execute(query)
            context["tasks"] = [
                {"id": str(t.id), "text": t.text, "priority": t.priority.value, "status": t.status.value}
                for t in result.scalars().all()
                if LEAD_TAG not in (t.tags or [])
            ]

        if "notes" in (agent.data_reads or []):
            result = await db.execute(
                select(Note).order_by(Note.updated_at.desc()).limit(20)
            )
            context["notes"] = [
                {"id": str(n.id), "title": n.title, "content": n.content[:200],
                 "tags": n.tags or [], "is_pinned": n.is_pinned}
                for n in result.scalars().all()
            ]

        if "leads" in (agent.data_reads or []):
            result = await db.execute(
                select(Task)
                .where(Task.status != TaskStatus.DONE)
                .order_by(Task.created_at.desc())
                .limit(200)
            )
            context["leads"] = [
                {"id": str(t.id), "title": t.text, "body": (t.description or "")[:200],
                 "url": t.url, "priority": t.priority.value, "tags": t.tags or []}
                for t in result.scalars().all()
                if LEAD_TAG in (t.tags or [])
            ][:50]

        if "marketing_content" in (agent.data_reads or []):
            from app.db.models import ContentStatus
            result = await db.execute(
                select(MarketingContent)
                .where(MarketingContent.status == ContentStatus.DRAFT)
                .order_by(MarketingContent.created_at.desc())
                .limit(20)
            )
            context["marketing_content"] = [
                {"id": str(c.id), "title": c.title, "body": c.body[:500],
                 "channel": c.channel, "status": c.status.value}
                for c in result.scalars().all()
            ]

        # Agent memory
        mem_result = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id == agent.id).order_by(AgentMemory.updated_at.desc())
        )
        memories = mem_result.scalars().all()
        if memories:
            context["memory"] = {m.key: m.value for m in memories}

        # Run history
        run_history = await db.execute(
            select(AgentRun).where(
                AgentRun.agent_id == agent.id,
                AgentRun.status == AgentRunStatus.COMPLETED,
            ).order_by(AgentRun.completed_at.desc()).limit(5)
        )
        past_runs = run_history.scalars().all()
        if past_runs:
            context["past_runs"] = [
                {
                    "run_date": r.completed_at.isoformat() if r.completed_at else None,
                    "trigger": r.trigger,
                    "summary": (r.output_data or {}).get("summary", "")[:300],
                    "action_count": len((r.output_data or {}).get("actions", [])),
                }
                for r in past_runs
            ]

        # Project context
        if agent.project_id:
            project = await db.get(Project, agent.project_id)
            if project:
                context["project"] = {
                    "id": str(project.id), "name": project.name,
                    "description": project.description, "status": project.status.value,
                }

        # Brand profile for marketing agents
        if any(r in (agent.data_reads or []) for r in ("leads", "marketing_content")):
            from app.db.models import BrandProfile
            bp_result = await db.execute(select(BrandProfile).limit(1))
            bp = bp_result.scalar_one_or_none()
            if bp:
                context["brand"] = {
                    "name": bp.name, "tone": bp.tone,
                    "topics": bp.topics or [],
                    "talking_points": bp.talking_points or {},
                    "avoid": bp.avoid or [],
                    "example_posts": bp.example_posts or [],
                }

        return context

    def render_prompt(self, template: str, context: dict) -> str:
        prompt = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            if isinstance(value, (dict, list)):
                prompt = prompt.replace(placeholder, json.dumps(value, indent=2))
            else:
                prompt = prompt.replace(placeholder, str(value))
        return prompt

    async def execute_with_agent_sdk(self, prompt: str, agent: AgentConfig) -> dict:
        from claude_agent_sdk import query, ClaudeAgentOptions

        tools = ["Read", "Glob"]
        if "bash" in (agent.tools or []):
            tools.append("Bash")
        if "web_search" in (agent.tools or []):
            tools.extend(["WebSearch", "WebFetch"])
        if "write" in (agent.tools or []):
            tools.extend(["Write", "Edit"])

        options_kwargs = {
            "system_prompt": self._build_system_prompt(agent),
            "max_turns": 10,
            # Only the granted tools exist for the agent, and all of them are pre-approved
            "tools": tools,
            "allowed_tools": tools,
            # Agents work in their own directory, never in the app's source tree
            "cwd": str(agent_workdir()),
            "setting_sources": ["project", "user"],
            "env": sdk_env(),
        }
        if agent.model:
            options_kwargs["model"] = agent.model
        if agent.max_budget_usd:
            options_kwargs["max_budget_usd"] = agent.max_budget_usd
        cli_path = shutil.which("claude")
        if cli_path:
            options_kwargs["cli_path"] = cli_path

        options = ClaudeAgentOptions(**options_kwargs)

        full_response = ""
        transcript = []
        result_message = None

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "total_cost_usd"):
                result_message = message
            if hasattr(message, "result") and message.result is not None:
                full_response = message.result
                if len(transcript) < 50:
                    transcript.append({"role": "result", "content": str(message.result)[:2000]})
            elif hasattr(message, "content"):
                text_parts = []
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                        full_response += block.text
                if text_parts and len(transcript) < 50:
                    role = getattr(message, 'role', 'assistant')
                    transcript.append({"role": role, "content": "".join(text_parts)[:2000]})

        self._last_transcript = transcript if transcript else None
        if result_message is not None:
            self._last_cost_usd = result_message.total_cost_usd or 0.0
            usage = result_message.usage or {}
            self._last_tokens = (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)
            if result_message.is_error and not result_message.result:
                raise RuntimeError(f"Agent run ended with {result_message.subtype}")

        if not full_response:
            return {"summary": "Agent produced no output", "actions": [], "raw": True}

        try:
            cleaned = full_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except (json.JSONDecodeError, IndexError):
            return {"summary": full_response, "actions": [], "raw": True}

    async def _execute_llm(self, prompt: str, agent: AgentConfig) -> dict:
        timeout_seconds = (agent.config or {}).get("timeout_seconds", 300)
        max_retries = 3
        base_delay = 2.0

        last_error = None
        for attempt in range(max_retries):
            try:
                return await asyncio.wait_for(
                    self.execute_with_agent_sdk(prompt, agent),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Agent {agent.name} timed out after {timeout_seconds}s.")
            except RuntimeError as e:
                err_msg = str(e)
                if any(kw in err_msg for kw in ["rate limit", "overloaded", "HTTP 5", "HTTP 429"]):
                    last_error = e
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Agent {agent.name} attempt {attempt + 1}/{max_retries} failed: {err_msg}. Retrying...")
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_error or RuntimeError(f"Agent {agent.name} failed after {max_retries} retries")

    async def start_run(
        self, agent: AgentConfig, trigger: str, db: AsyncSession, notify: bool = False,
        task_id: UUID | None = None,
    ) -> AgentRun:
        """Run an agent to completion in the given session and commit the result.

        notify=True sends the outcome to Telegram right away (used for runs a
        person asked for); otherwise completions go into the morning briefing.
        With task_id the agent works on that assigned task instead of its
        scheduled job, and answers in the task's thread.
        """
        # Plain copies: after a rollback the ORM object can't be read without awaiting
        agent_id, agent_name, agent_slug = agent.id, agent.name, agent.slug
        now = datetime.now(timezone.utc)
        run = AgentRun(agent_id=agent.id, trigger=trigger, status=AgentRunStatus.RUNNING, started_at=now)
        db.add(run)
        agent.status = AgentStatus.RUNNING
        # Recorded at start so a failing interval agent waits a full interval before retrying
        agent.last_run_at = now
        await db.commit()
        run_id = run.id

        await broadcast("agent.started", {"agent_id": str(agent.id), "run_id": str(run.id)})

        try:
            context = await self.build_context(agent, db)
            task = None
            if task_id:
                task = await db.get(Task, task_id)
                if not task:
                    raise RuntimeError(f"Task {task_id} not found")
                thread = await threads.load_thread(db, task_id)
                prompt = threads.assignment_prompt(agent, task, thread, context)
            else:
                prompt = self.render_prompt(agent.prompt_template, context)
            run.input_data = {
                "prompt_length": len(prompt), "context_keys": list(context.keys()),
                "task_id": str(task_id) if task_id else None,
            }

            result = await self._execute_llm(prompt, agent)

            # Validate output
            validated, validation_warnings = validate_agent_output(result)
            actions = [a.model_dump(exclude_none=True) for a in validated.actions]
            max_actions = _max_actions(agent)
            if max_actions is not None and len(actions) > max_actions:
                validation_warnings.append(f"{len(actions) - max_actions} actions over the limit of {max_actions} were dropped")
                actions = actions[:max_actions]
            if validation_warnings:
                logger.warning(f"Agent {agent.name} output warnings: {validation_warnings}")
                result["warnings"] = validation_warnings

            # Update run
            run.status = AgentRunStatus.COMPLETED
            run.output_data = result
            run.completed_at = datetime.now(timezone.utc)
            run.cost_usd = self._last_cost_usd
            run.tokens_used = self._last_tokens
            run.transcript = self._last_transcript
            agent.status = AgentStatus.IDLE

            # Process actions (approval or direct)
            requires_approval = (agent.config or {}).get("requires_approval", False)
            summary = result.get("summary", "")

            if requires_approval and actions:
                approval = AgentApproval(
                    run_id=run.id, agent_id=agent.id,
                    actions=actions, summary=summary,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )
                db.add(approval)
                await db.flush()
                text, markup = review.approval_message(approval, agent.name)
                await create_notification(
                    db, title=f"{agent.name} wants to take {len(actions)} action{'s' if len(actions) != 1 else ''}",
                    body=summary[:300], category="approval",
                    source=f"agent:{agent.slug}", priority="urgent",
                    # Sent to Telegram as-is, with Approve / Reject buttons
                    data={"telegram_text": text, "reply_markup": markup},
                )
                await broadcast("approval.pending", {
                    "agent_id": str(agent.id), "action_count": len(actions),
                })
            else:
                await self.process_actions(actions, agent, db)

            await broadcast("agent.completed", {"agent_id": str(agent.id), "summary": summary})

            prefs = await get_notification_prefs_dict(db)
            if task:
                # The reply in the thread (also sent to Telegram) is the notification
                await threads.post_agent_reply(db, task, agent, result, run)
                await broadcast("task.updated", {"id": str(task.id)})
            elif notify or prefs.get("agent_completions", True):
                await create_notification(
                    db, title=f"{agent.name} finished",
                    body=summary[:500], category="success", source=f"agent:{agent.slug}",
                    priority="urgent" if notify else "routine",
                )

        except asyncio.CancelledError:
            await db.rollback()
            await self._finish_failed(db, run_id, agent_id, AgentRunStatus.CANCELLED, "Stopped by user")
            if task_id:
                # A non-user last comment keeps the scheduler from restarting it
                db.add(TaskComment(task_id=task_id, author=threads.SYSTEM, body=f"{agent_name} was stopped."))
                await db.commit()
            raise

        except Exception as e:
            logger.error(f"Agent {agent_name} run failed: {e}")
            await db.rollback()
            await self._finish_failed(db, run_id, agent_id, AgentRunStatus.FAILED, str(e))
            await broadcast("agent.failed", {"agent_id": str(agent_id), "error": str(e)})
            prefs = await get_notification_prefs_dict(db)
            if task_id:
                await threads.post_run_failure(db, task_id, agent_name, str(e))
            elif notify or prefs.get("agent_failures", True):
                await create_notification(
                    db, title=f"{agent_name} failed",
                    body=str(e)[:200], category="error",
                    source=f"agent:{agent_slug}", priority="urgent",
                )

        run = await db.get(AgentRun, run_id)
        db.add(EventLog(
            event_type=f"agent.run.{run.status.value}",
            entity_type="agent", entity_id=agent_id,
            source=f"agent:{agent_slug}",
            data={"run_id": str(run.id), "trigger": trigger},
        ))
        await db.commit()
        self._last_transcript = None
        return run

    async def _finish_failed(self, db: AsyncSession, run_id, agent_id, status: AgentRunStatus, error: str):
        run = await db.get(AgentRun, run_id)
        agent = await db.get(AgentConfig, agent_id)
        run.status = status
        run.error = error
        run.transcript = self._last_transcript
        run.completed_at = datetime.now(timezone.utc)
        agent.status = AgentStatus.IDLE if status == AgentRunStatus.CANCELLED else AgentStatus.ERROR
        await db.commit()

    async def process_actions(self, actions: list, agent: AgentConfig, db: AsyncSession) -> list[str]:
        """Apply validated agent actions. Returns warnings for actions that were skipped."""
        lead_count = 0
        content_count = 0
        warnings = []

        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                continue
            action_type = action.get("type", "")
            try:
                applied = await self._apply_action(action, agent, db)
            except ValueError as e:
                warnings.append(f"Action {i} ({action_type}) skipped: {e}")
                continue
            if not applied:
                warnings.append(f"Action {i} ({action_type}) skipped: agent has no write access")
            elif action_type == "create_lead":
                lead_count += 1
            elif action_type == "create_content":
                content_count += 1

        if warnings:
            logger.warning(f"Agent {agent.name}: {warnings}")

        # Batched notifications
        prefs = await get_notification_prefs_dict(db)
        if lead_count and prefs.get("signal_summary", True):
            await create_notification(
                db, title=f"Found {lead_count} new lead{'s' if lead_count > 1 else ''}",
                category="lead", source=f"agent:{agent.slug}",
            )
        if content_count and prefs.get("content_drafts", True):
            await create_notification(
                db, title=f"{content_count} new draft{'s' if content_count > 1 else ''} ready",
                category="content", source=f"agent:{agent.slug}",
            )
        return warnings

    async def _apply_action(self, action: dict, agent: AgentConfig, db: AsyncSession) -> bool:
        """Apply one action. Returns False if the agent may not write this kind of data;
        raises ValueError if the action is malformed."""
        writes = agent.data_writes or []
        action_type = action.get("type", "")

        if action_type == "create_task":
            if "tasks" not in writes:
                return False
            task = Task(
                text=action.get("text") or action.get("title") or "Untitled task",
                description=action.get("description"),
                priority=_enum(TaskPriority, action.get("priority"), TaskPriority.MEDIUM),
                project_id=agent.project_id,
                source=f"agent:{agent.slug}",
                tags=action.get("tags", []),
            )
            db.add(task)
            await db.flush()
            await broadcast("task.created", {"id": str(task.id), "text": task.text, "source": task.source})

        elif action_type == "update_task":
            if "tasks" not in writes:
                return False
            task = await db.get(Task, _uuid(action.get("task_id")))
            if not task:
                raise ValueError(f"task {action.get('task_id')} not found")
            if action.get("status"):
                task.status = _enum(TaskStatus, action["status"])
                task.completed_at = datetime.now(timezone.utc) if task.status == TaskStatus.DONE else None
            if action.get("priority"):
                task.priority = _enum(TaskPriority, action["priority"])

        elif action_type == "create_note":
            if "notes" not in writes:
                return False
            db.add(Note(
                title=action.get("title", "Untitled"),
                content=action.get("content", ""),
                tags=action.get("tags", []),
                project_id=agent.project_id,
                source=f"agent:{agent.slug}",
            ))
            await db.flush()

        elif action_type == "save_memory":
            key, value = action.get("key"), action.get("value")
            if not key or not value:
                raise ValueError("save_memory needs key and value")
            existing = await db.execute(
                select(AgentMemory).where(AgentMemory.agent_id == agent.id, AgentMemory.key == key)
            )
            mem = existing.scalar_one_or_none()
            if mem:
                mem.value = str(value)
            else:
                db.add(AgentMemory(
                    agent_id=agent.id, key=key, value=str(value),
                    memory_type=action.get("memory_type", "general"),
                ))

        elif action_type == "create_lead":
            if "tasks" not in writes:
                return False
            lead = Task(
                text=action.get("title") or action.get("text") or "Untitled lead",
                description=action.get("body", ""),
                url=action.get("url"),
                priority=_lead_priority(action.get("relevance_score")),
                project_id=agent.project_id,
                source=f"agent:{agent.slug}",
                tags=_lead_tags(action),
            )
            db.add(lead)
            await db.flush()
            await broadcast("task.created", {"id": str(lead.id), "text": lead.text, "source": lead.source})

        elif action_type == "create_content":
            if "marketing_content" not in writes:
                return False
            task_id = _uuid(action["task_id"]) if action.get("task_id") else None
            if task_id and not await db.get(Task, task_id):
                task_id = None
            content = MarketingContent(
                title=action.get("title", "Untitled content"),
                body=action.get("body", ""),
                channel=action.get("channel", "other"),
                source=f"agent:{agent.slug}",
                task_id=task_id,
                project_id=agent.project_id,
                agent_id=agent.id,
                tags=action.get("tags", []),
            )
            db.add(content)
            await db.flush()
            await broadcast("content.created", {"id": str(content.id), "title": content.title})

        return True


def _lead_priority(relevance) -> str:
    try:
        score = float(relevance)
    except (TypeError, ValueError):
        return "medium"
    if score >= 0.8:
        return "high"
    if score < 0.5:
        return "low"
    return "medium"


def _lead_tags(action: dict) -> list[str]:
    tags = [LEAD_TAG]
    if action.get("source_type"):
        tags.append(str(action["source_type"]))
    for tag in action.get("tags") or []:
        if tag not in tags:
            tags.append(tag)
    return tags


def _enum(enum_cls, value, default=None):
    if value is None and default is not None:
        return default
    try:
        return enum_cls(str(value).lower())
    except ValueError:
        raise ValueError(f"invalid {enum_cls.__name__} '{value}'")


def _uuid(value) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"invalid id '{value}'")


def _max_actions(agent: AgentConfig) -> int | None:
    config = agent.config or {}
    limit = config.get("max_actions_per_run", config.get("max_actions"))
    try:
        return int(limit) if limit is not None else None
    except (TypeError, ValueError):
        return None


def agent_workdir() -> Path:
    path = Path(settings.agent_workdir)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def sdk_env() -> dict:
    env = dict(os.environ)
    if settings.claude_code_oauth_token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token
    return env


# --- Background runs ---------------------------------------------------------
# Agent runs take minutes, so callers (Telegram, the API, the scheduler) start
# them in the background. The app is a single process, so an in-memory map of
# agent id -> task is enough to prevent duplicate runs and to support stop.

_active_runs: dict[UUID, asyncio.Task] = {}


def is_running(agent_id: UUID) -> bool:
    return agent_id in _active_runs


def start_background_run(
    agent_id: UUID, trigger: str, notify: bool = False, task_id: UUID | None = None,
) -> bool:
    """Start an agent run in the background. Returns False if it is already running."""
    if agent_id in _active_runs:
        return False
    task = asyncio.create_task(_run_in_background(agent_id, trigger, notify, task_id))
    _active_runs[agent_id] = task
    task.add_done_callback(lambda _: _active_runs.pop(agent_id, None))
    return True


async def cancel_run(agent_id: UUID) -> bool:
    task = _active_runs.get(agent_id)
    if not task:
        return False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return True


async def _run_in_background(agent_id: UUID, trigger: str, notify: bool, task_id: UUID | None):
    async with async_session() as db:
        agent = await db.get(AgentConfig, agent_id)
        if not agent or agent.status == AgentStatus.DISABLED:
            return
        try:
            await AgentRunner().start_run(agent, trigger=trigger, db=db, notify=notify, task_id=task_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(f"Background run of {agent.name} crashed")


async def recover_interrupted_runs():
    """On startup, close out runs that were in flight when the app stopped."""
    async with async_session() as db:
        runs = (await db.execute(
            select(AgentRun).where(AgentRun.status.in_([AgentRunStatus.RUNNING, AgentRunStatus.PENDING]))
        )).scalars().all()
        for run in runs:
            run.status = AgentRunStatus.FAILED
            run.error = "Interrupted by an app restart"
            run.completed_at = datetime.now(timezone.utc)
        agents = (await db.execute(
            select(AgentConfig).where(AgentConfig.status == AgentStatus.RUNNING)
        )).scalars().all()
        for agent in agents:
            agent.status = AgentStatus.IDLE
        await db.commit()
        if runs or agents:
            logger.info(f"Recovered {len(runs)} interrupted runs, reset {len(agents)} agents")
