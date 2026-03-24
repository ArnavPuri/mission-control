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
    AgentApproval, ApprovalStatus,
    AgentMemory, Note,
)
from app.api.ws import broadcast
from app.api.notifications import create_notification
from app.orchestrator.schemas import validate_agent_output

logger = logging.getLogger(__name__)


class AgentRunner:
    """Executes agent runs against the Claude Agent SDK or Anthropic API."""

    def __init__(self):
        self._last_session_id = None
        self._last_message_uuid = None
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
            "\n## Time Awareness\n"
            'Your context includes "time_context" with the current UTC time and period. '
            "Adapt your behavior accordingly:\n"
            "- Morning: planning, prioritization, daily briefings\n"
            "- Afternoon: execution, progress updates\n"
            "- Evening: reflection, reviews, day summaries\n"
            "- Night: quiet background tasks, prep for tomorrow"
        )

        parts.append(
            "\n## Memory & Learning\n"
            "You have persistent memory that survives between runs. Use it.\n"
            '- Your context includes "past_runs" showing your last 5 runs.\n'
            '- Your "memory" dict contains things you saved previously.\n'
            '- Your "shared_memory" dict contains notes from other agents.\n'
            "- To remember something, include a save_memory action.\n"
            "- To share context, include a save_shared_memory action.\n"
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

        if "marketing_signals" in (agent.data_reads or []):
            from app.db.models import MarketingSignal, SignalStatus
            result = await db.execute(
                select(MarketingSignal)
                .where(MarketingSignal.status == SignalStatus.NEW)
                .order_by(MarketingSignal.created_at.desc())
                .limit(50)
            )
            context["marketing_signals"] = [
                {"id": str(s.id), "title": s.title, "body": s.body[:200],
                 "source_type": s.source_type, "source_url": s.source_url,
                 "relevance_score": s.relevance_score, "signal_type": s.signal_type}
                for s in result.scalars().all()
            ]

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

        # Standup context
        if "standup" in (agent.data_reads or []):
            cutoff = datetime.now(timezone.utc) - timedelta(hours=36)
            all_agents_result = await db.execute(
                select(AgentConfig).where(AgentConfig.status != AgentStatus.DISABLED)
            )
            all_agents = all_agents_result.scalars().all()

            standup_roster = []
            for a in all_agents:
                if a.id == agent.id:
                    continue

                agent_info = {
                    "name": a.name, "slug": a.slug, "description": a.description,
                    "status": a.status.value, "model": a.model,
                    "schedule": f"{a.schedule_type}:{a.schedule_value}" if a.schedule_type else "manual",
                    "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
                }

                last_run_result = await db.execute(
                    select(AgentRun).where(
                        AgentRun.agent_id == a.id,
                        AgentRun.status == AgentRunStatus.COMPLETED,
                        AgentRun.completed_at >= cutoff,
                    ).order_by(AgentRun.completed_at.desc()).limit(1)
                )
                last_run = last_run_result.scalar_one_or_none()
                if last_run:
                    agent_info["last_run"] = {
                        "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
                        "summary": (last_run.output_data or {}).get("summary", "")[:300],
                        "action_count": len((last_run.output_data or {}).get("actions", [])),
                    }

                standup_roster.append(agent_info)

            context["standup"] = standup_roster

        # Time context
        now = datetime.now(timezone.utc)
        hour = now.hour
        if hour < 6:
            time_period, time_guidance = "late_night", "Focus on background tasks."
        elif hour < 12:
            time_period, time_guidance = "morning", "Good time for planning and prioritization."
        elif hour < 17:
            time_period, time_guidance = "afternoon", "Focus on execution and progress."
        elif hour < 21:
            time_period, time_guidance = "evening", "Good time for reflection and reviews."
        else:
            time_period, time_guidance = "night", "Focus on quiet tasks and prep for tomorrow."

        context["time_context"] = {
            "utc_time": now.isoformat(),
            "hour": hour,
            "period": time_period,
            "day_of_week": now.strftime("%A").lower(),
            "guidance": time_guidance,
        }

        # Agent memory
        mem_result = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id == agent.id).order_by(AgentMemory.updated_at.desc())
        )
        memories = mem_result.scalars().all()
        if memories:
            context["memory"] = {m.key: m.value for m in memories}

        # Shared scratchpad
        shared_result = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id.is_(None)).order_by(AgentMemory.updated_at.desc())
        )
        shared_memories = shared_result.scalars().all()
        if shared_memories:
            context["shared_memory"] = {m.key: m.value for m in shared_memories}

        # Lessons
        lessons_result = await db.execute(
            select(AgentMemory).where(
                AgentMemory.agent_id.is_(None),
                AgentMemory.key == "system:lessons",
            )
        )
        lessons_mem = lessons_result.scalar_one_or_none()
        if lessons_mem and lessons_mem.value.strip():
            context["lessons"] = lessons_mem.value

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
        if any(r in (agent.data_reads or []) for r in ("marketing_signals", "marketing_content")):
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
        if not cli_path:
            # Fallback: the claude_agent_sdk bundles a CLI binary
            import claude_agent_sdk
            bundled = os.path.join(os.path.dirname(claude_agent_sdk.__file__), "_bundled", "claude")
            if os.path.isfile(bundled):
                cli_path = bundled
        if cli_path:
            options_kwargs["cli_path"] = cli_path

        # Session resumption
        use_resume = False
        if agent.session_id and agent.session_expires_at and agent.session_expires_at > datetime.now(timezone.utc):
            options_kwargs["resume"] = agent.session_id
            if agent.last_message_uuid:
                options_kwargs["resume_session_at"] = agent.last_message_uuid

        options = ClaudeAgentOptions(**options_kwargs)

        full_response = ""
        new_session_id = None
        last_assistant_uuid = None
        transcript = []

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'subtype') and message.subtype == 'init':
                if hasattr(message, 'session_id'):
                    new_session_id = message.session_id
                elif hasattr(message, 'data') and isinstance(message.data, dict):
                    new_session_id = message.data.get('session_id')

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
                    if role == "assistant":
                        for attr in ('uuid', 'id', 'message_id'):
                            if hasattr(message, attr):
                                last_assistant_uuid = getattr(message, attr)
                                break

        self._last_session_id = new_session_id
        self._last_message_uuid = last_assistant_uuid
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

            # Session persistence
            if agent.session_window_days and agent.session_window_days > 0:
                if self._last_session_id:
                    agent.session_id = self._last_session_id
                if self._last_message_uuid:
                    agent.last_message_uuid = self._last_message_uuid
                agent.session_expires_at = datetime.now(timezone.utc) + timedelta(days=agent.session_window_days)

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

            # Post-run learning
            await self._post_run_learn(agent, run, result, db)

            # Agent chaining
            chain_to = agent.config.get("chain_to") if agent.config else None
            if chain_to:
                try:
                    chain_result = await db.execute(
                        select(AgentConfig).where(AgentConfig.slug == chain_to)
                    )
                    next_agent = chain_result.scalar_one_or_none()
                    if next_agent and next_agent.status != AgentStatus.RUNNING:
                        asyncio.create_task(self._chain_run(next_agent.id, result, trigger))
                except Exception as e:
                    logger.warning(f"Agent chaining failed: {e}")

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

        self._last_session_id = None
        self._last_message_uuid = None
        self._last_transcript = None

        db.add(EventLog(
            event_type=f"agent.run.{run.status.value}",
            entity_type="agent", entity_id=agent.id,
            source=f"agent:{agent.slug}",
            data={"run_id": str(run.id), "trigger": trigger},
        ))
        await db.flush()

        return run

    async def _chain_run(self, next_agent_id, previous_result: dict, trigger: str):
        from app.db.session import async_session
        async with async_session() as db:
            next_agent = await db.get(AgentConfig, next_agent_id)
            if not next_agent or next_agent.status == AgentStatus.RUNNING:
                return
            existing = await db.execute(
                select(AgentMemory).where(
                    AgentMemory.agent_id == next_agent.id,
                    AgentMemory.key == "_chain_input",
                )
            )
            mem = existing.scalar_one_or_none()
            chain_data = json.dumps(previous_result)[:2000]
            if mem:
                mem.value = chain_data
            else:
                db.add(AgentMemory(
                    agent_id=next_agent.id, key="_chain_input",
                    value=chain_data, memory_type="chain",
                ))
            await self.start_run(next_agent, trigger=f"chain:{trigger}", db=db)
            await db.commit()

    async def _post_run_learn(self, agent: AgentConfig, run: AgentRun, result: dict, db: AsyncSession):
        try:
            actions = result.get("actions", [])
            action_types = [a.get("type", "") for a in actions if isinstance(a, dict)]

            # Run counter
            counter_result = await db.execute(
                select(AgentMemory).where(AgentMemory.agent_id == agent.id, AgentMemory.key == "_run_count")
            )
            counter = counter_result.scalar_one_or_none()
            run_count = int(counter.value) + 1 if counter else 1
            if counter:
                counter.value = str(run_count)
            else:
                db.add(AgentMemory(agent_id=agent.id, key="_run_count", value=str(run_count), memory_type="system"))

            # Last summary
            last_summary = result.get("summary", "")[:500]
            if last_summary:
                existing = await db.execute(
                    select(AgentMemory).where(AgentMemory.agent_id == agent.id, AgentMemory.key == "_last_run_summary")
                )
                mem = existing.scalar_one_or_none()
                if mem:
                    mem.value = last_summary
                else:
                    db.add(AgentMemory(agent_id=agent.id, key="_last_run_summary", value=last_summary, memory_type="system"))

            await db.flush()
        except Exception as e:
            logger.debug(f"Post-run learning failed for {agent.name}: {e}")

    async def _write_lesson(self, agent_name: str, lesson_text: str, db: AsyncSession):
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_lesson = f"[{date_str}] {agent_name}: {lesson_text}"

        existing = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id.is_(None), AgentMemory.key == "system:lessons")
        )
        mem = existing.scalar_one_or_none()

        if mem:
            lines = [l for l in mem.value.split("\n") if l.strip()]
            lines.append(new_lesson)
            if len(lines) > 20:
                lines = lines[-20:]
            mem.value = "\n".join(lines)
        else:
            db.add(AgentMemory(agent_id=None, key="system:lessons", value=new_lesson, memory_type="shared"))

    async def _process_actions(self, actions: list, agent: AgentConfig, db: AsyncSession):
        _signal_count = 0
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

            elif action_type == "save_shared_memory":
                key = action.get("key")
                value = action.get("value")
                if key and value:
                    existing = await db.execute(
                        select(AgentMemory).where(AgentMemory.agent_id.is_(None), AgentMemory.key == key)
                    )
                    mem = existing.scalar_one_or_none()
                    if mem:
                        mem.value = str(value)
                    else:
                        db.add(AgentMemory(agent_id=None, key=key, value=str(value), memory_type="shared"))

            elif action_type == "create_signal" and "marketing_signals" in (agent.data_writes or []):
                from app.db.models import MarketingSignal
                signal = MarketingSignal(
                    title=action.get("title", "Untitled signal"),
                    body=action.get("body", ""),
                    source=f"agent:{agent.slug}",
                    source_type=action.get("source_type", "other"),
                    source_url=action.get("source_url"),
                    relevance_score=min(max(action.get("relevance_score", 0.5), 0.0), 1.0),
                    signal_type=action.get("signal_type", "opportunity"),
                    channel_metadata=action.get("channel_metadata", {}),
                    project_id=agent.project_id,
                    agent_id=agent.id,
                    tags=action.get("tags", []),
                )
                db.add(signal)
                await db.flush()
                await broadcast("signal.created", {"id": str(signal.id), "title": signal.title})
                _signal_count += 1

            elif action_type == "create_content" and "marketing_content" in (agent.data_writes or []):
                from app.db.models import MarketingContent
                content = MarketingContent(
                    title=action.get("title", "Untitled content"),
                    body=action.get("body", ""),
                    channel=action.get("channel", "other"),
                    source=f"agent:{agent.slug}",
                    signal_id=UUID(action["signal_id"]) if action.get("signal_id") else None,
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

        if _signal_count > 0 and prefs.get("signal_summary", True):
            await create_notification(
                db, title=f"Found {_signal_count} new leads",
                category="signal", source=f"agent:{agent.slug}",
                priority="routine",
            )

        if _content_count > 0 and prefs.get("content_drafts", True):
            await create_notification(
                db, title=f"{_content_count} new draft{'s' if _content_count > 1 else ''} ready",
                category="content", source=f"agent:{agent.slug}",
            )
