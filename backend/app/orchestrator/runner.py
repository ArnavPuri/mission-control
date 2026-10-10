"""
Agent Runner - Executes agents using the Claude Agent SDK.

Uses Claude Code subscription (OAuth) exclusively.
"""

import asyncio
import json
import os
import logging
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    AgentConfig, AgentRun, AgentStatus, AgentRunStatus,
    Project, Task, EventLog, TaskStatus,
    AgentApproval, AgentMemory, Note, LEAD_TAG,
)
from app.api.ws import broadcast
from app.api.notifications import create_notification
from app.orchestrator.schemas import validate_agent_output

logger = logging.getLogger(__name__)


class AgentRunner:
    """Executes agent runs against the Claude Agent SDK."""

    def __init__(self):
        self._last_transcript = None

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
            from app.db.models import MarketingContent, ContentStatus
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
        import shutil

        options_kwargs = {
            "system_prompt": self._build_system_prompt(agent),
            "max_turns": 10,
            "setting_sources": ["project", "user"],
        }

        if agent.model:
            options_kwargs["model"] = agent.model
        if agent.max_budget_usd:
            options_kwargs["max_budget_usd"] = agent.max_budget_usd

        allowed_tools = ["Read", "Glob"]
        if "bash" in (agent.tools or []):
            allowed_tools.append("Bash")
        if "web_search" in (agent.tools or []):
            allowed_tools.append("WebSearch")
        if "write" in (agent.tools or []):
            allowed_tools.extend(["Write", "Edit"])
        options_kwargs["allowed_tools"] = allowed_tools

        env = dict(os.environ)
        if settings.claude_code_oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token
        options_kwargs["env"] = env

        cli_path = shutil.which("claude")
        if cli_path:
            options_kwargs["cli_path"] = cli_path

        options = ClaudeAgentOptions(**options_kwargs)

        full_response = ""
        transcript = []

        async for message in query(prompt=prompt, options=options):
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

    async def start_run(self, agent: AgentConfig, trigger: str, db: AsyncSession) -> AgentRun:
        """Start an agent run."""
        run = AgentRun(agent_id=agent.id, trigger=trigger, status=AgentRunStatus.RUNNING)
        db.add(run)
        agent.status = AgentStatus.RUNNING
        await db.flush()

        await broadcast("agent.started", {"agent_id": str(agent.id), "run_id": str(run.id)})

        try:
            context = await self.build_context(agent, db)
            prompt = self.render_prompt(agent.prompt_template, context)
            run.input_data = {"prompt_length": len(prompt), "context_keys": list(context.keys())}

            result = await self._execute_llm(prompt, agent)

            # Validate output
            validated, validation_warnings = validate_agent_output(result)
            if validation_warnings:
                logger.warning(f"Agent {agent.name} output warnings: {validation_warnings}")

            # Update run
            run.status = AgentRunStatus.COMPLETED
            run.output_data = result
            run.completed_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.IDLE
            agent.last_run_at = datetime.now(timezone.utc)
            run.transcript = self._last_transcript

            # Process actions (approval or direct)
            requires_approval = agent.config.get("requires_approval", False) if agent.config else False
            actions = [a.model_dump(exclude_none=True) for a in validated.actions]

            if requires_approval and actions:
                approval = AgentApproval(
                    run_id=run.id, agent_id=agent.id,
                    actions=actions, summary=result.get("summary", ""),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )
                db.add(approval)
                await broadcast("approval.pending", {
                    "agent_id": str(agent.id), "action_count": len(actions),
                })
            else:
                await self._process_actions(actions, agent, db)

            await broadcast("agent.completed", {
                "agent_id": str(agent.id), "summary": result.get("summary", ""),
            })

            # Notification
            try:
                from app.api.brand import get_notification_prefs_dict
                prefs = await get_notification_prefs_dict(db)
                if prefs.get("agent_completions", True):
                    await create_notification(
                        db, title=f"{agent.name} completed",
                        body=result.get("summary", "")[:200],
                        category="success", source=f"agent:{agent.slug}",
                    )
            except Exception:
                pass

        except Exception as e:
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.transcript = self._last_transcript
            run.completed_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.ERROR
            logger.error(f"Agent {agent.name} run failed: {e}")

            await broadcast("agent.failed", {"agent_id": str(agent.id), "error": str(e)})

            try:
                from app.api.brand import get_notification_prefs_dict
                prefs = await get_notification_prefs_dict(db)
                if prefs.get("agent_failures", True):
                    await create_notification(
                        db, title=f"{agent.name} failed",
                        body=str(e)[:200], category="error",
                        source=f"agent:{agent.slug}", priority="urgent",
                    )
            except Exception:
                pass

        await db.flush()

        self._last_transcript = None

        db.add(EventLog(
            event_type=f"agent.run.{run.status.value}",
            entity_type="agent", entity_id=agent.id,
            source=f"agent:{agent.slug}",
            data={"run_id": str(run.id), "trigger": trigger},
        ))
        await db.flush()

        return run

    async def _process_actions(self, actions: list, agent: AgentConfig, db: AsyncSession):
        _lead_count = 0
        _content_count = 0

        for action in actions:
            if not isinstance(action, dict):
                continue

            action_type = action.get("type", "")

            if action_type == "create_task" and "tasks" in (agent.data_writes or []):
                task = Task(
                    text=action.get("text", "Untitled task"),
                    priority=action.get("priority", "medium"),
                    project_id=agent.project_id,
                    source=f"agent:{agent.slug}",
                    tags=action.get("tags", []),
                )
                db.add(task)
                await db.flush()
                await broadcast("task.created", {"text": task.text, "source": task.source})

            elif action_type == "update_task" and "tasks" in (agent.data_writes or []):
                task_id = action.get("task_id")
                if task_id:
                    task = await db.get(Task, UUID(task_id))
                    if task:
                        if "status" in action:
                            task.status = action["status"]
                        if "priority" in action:
                            task.priority = action["priority"]

            elif action_type == "create_note" and "notes" in (agent.data_writes or []):
                note = Note(
                    title=action.get("title", "Untitled"),
                    content=action.get("content", ""),
                    tags=action.get("tags", []),
                    source=f"agent:{agent.slug}",
                )
                db.add(note)
                await db.flush()

            elif action_type == "save_memory":
                key = action.get("key")
                value = action.get("value")
                if key and value:
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

            elif action_type == "create_lead" and "tasks" in (agent.data_writes or []):
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
                _lead_count += 1

            elif action_type == "create_content" and "marketing_content" in (agent.data_writes or []):
                from app.db.models import MarketingContent
                content = MarketingContent(
                    title=action.get("title", "Untitled content"),
                    body=action.get("body", ""),
                    channel=action.get("channel", "other"),
                    source=f"agent:{agent.slug}",
                    task_id=UUID(action["task_id"]) if action.get("task_id") else None,
                    project_id=agent.project_id,
                    agent_id=agent.id,
                    tags=action.get("tags", []),
                )
                db.add(content)
                await db.flush()
                await broadcast("content.created", {"id": str(content.id), "title": content.title})
                _content_count += 1

        # Batched notifications
        from app.api.brand import get_notification_prefs_dict
        prefs = await get_notification_prefs_dict(db)

        if _lead_count > 0 and prefs.get("signal_summary", True):
            await create_notification(
                db, title=f"Found {_lead_count} new lead{'s' if _lead_count > 1 else ''}",
                category="lead", source=f"agent:{agent.slug}",
                priority="routine",
            )

        if _content_count > 0 and prefs.get("content_drafts", True):
            await create_notification(
                db, title=f"{_content_count} new draft{'s' if _content_count > 1 else ''} ready",
                category="content", source=f"agent:{agent.slug}",
            )


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
