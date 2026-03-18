"""
Agent Runner - Executes agents using the Claude Agent SDK.

Supports multiple auth methods:
  - ANTHROPIC_API_KEY (standard API)
  - CLAUDE_CODE_OAUTH_TOKEN (subscription-based)
  - Falls back to direct Anthropic SDK for non-Agent-SDK providers

Each agent run:
  1. Loads agent config from DB
  2. Builds context from DB (projects, tasks, etc.)
  3. Renders the prompt template with context
  4. Executes via Claude Agent SDK
  5. Parses structured output
  6. Writes results back to DB
  7. Logs the run
"""

import asyncio
import json
import os
import logging
import random
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, LLMProvider
from app.db.models import (
    AgentConfig, AgentRun, AgentStatus, AgentRunStatus,
    Project, Task, Idea, ReadingItem, EventLog, TaskStatus,
    Habit, Goal, JournalEntry, AgentApproval, ApprovalStatus,
    AgentMemory,
)
from app.api.ws import broadcast
from app.orchestrator.schemas import validate_agent_output

logger = logging.getLogger(__name__)


class AgentRunner:
    """Executes agent runs against the Claude Agent SDK or Anthropic API."""

    async def build_context(self, agent: AgentConfig, db: AsyncSession) -> dict:
        """Build the data context an agent needs based on its data_reads config."""
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

        if "ideas" in (agent.data_reads or []):
            result = await db.execute(select(Idea).order_by(Idea.created_at.desc()).limit(50))
            context["ideas"] = [
                {"id": str(i.id), "text": i.text, "tags": i.tags or []}
                for i in result.scalars().all()
            ]

        if "reading" in (agent.data_reads or []):
            result = await db.execute(select(ReadingItem).where(ReadingItem.is_read == False))
            context["reading"] = [
                {"id": str(r.id), "title": r.title, "url": r.url}
                for r in result.scalars().all()
            ]

        if "habits" in (agent.data_reads or []):
            result = await db.execute(select(Habit).where(Habit.is_active == True))
            context["habits"] = [
                {"id": str(h.id), "name": h.name, "current_streak": h.current_streak, "best_streak": h.best_streak}
                for h in result.scalars().all()
            ]

        if "goals" in (agent.data_reads or []):
            from app.db.models import GoalStatus
            result = await db.execute(select(Goal).where(Goal.status == GoalStatus.ACTIVE))
            context["goals"] = [
                {"id": str(g.id), "title": g.title, "description": g.description, "progress": g.progress}
                for g in result.scalars().all()
            ]

        if "journal" in (agent.data_reads or []):
            result = await db.execute(
                select(JournalEntry).order_by(JournalEntry.created_at.desc()).limit(7)
            )
            context["journal"] = [
                {"id": str(j.id), "content": j.content[:200], "mood": j.mood.value if j.mood else None,
                 "created_at": j.created_at.isoformat()}
                for j in result.scalars().all()
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

        # Load agent memory (persistent context from previous runs)
        mem_result = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id == agent.id).order_by(AgentMemory.updated_at.desc())
        )
        memories = mem_result.scalars().all()
        if memories:
            context["memory"] = {m.key: m.value for m in memories}

        # Include project-specific context if agent is bound to a project
        if agent.project_id:
            project = await db.get(Project, agent.project_id)
            if project:
                context["project"] = {
                    "id": str(project.id),
                    "name": project.name,
                    "description": project.description,
                    "status": project.status.value,
                }

        return context

    def render_prompt(self, template: str, context: dict) -> str:
        """Simple Jinja-style {{var}} template rendering."""
        prompt = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            if isinstance(value, (dict, list)):
                prompt = prompt.replace(placeholder, json.dumps(value, indent=2))
            else:
                prompt = prompt.replace(placeholder, str(value))
        return prompt

    async def execute_with_agent_sdk(self, prompt: str, agent: AgentConfig) -> dict:
        """Execute using Claude Agent SDK (supports both API key and OAuth)."""
        from claude_agent_sdk import query, ClaudeAgentOptions

        # Build options
        options_kwargs = {
            "system_prompt": (
                f"You are {agent.name}, a specialized AI agent.\n"
                f"Role: {agent.description}\n"
                f"You MUST respond with valid JSON only. No markdown, no explanation.\n"
                f"Your output should contain an 'actions' array of things you did or recommend,\n"
                f"and a 'summary' string describing what you accomplished."
            ),
            "max_turns": 10,
        }

        if agent.model:
            options_kwargs["model"] = agent.model

        if agent.max_budget_usd:
            options_kwargs["max_budget_usd"] = agent.max_budget_usd

        # Map agent tools to SDK allowed tools
        allowed_tools = ["Read", "Glob"]  # baseline read-only
        if "bash" in (agent.tools or []):
            allowed_tools.append("Bash")
        if "web_search" in (agent.tools or []):
            allowed_tools.append("WebSearch")
        if "write" in (agent.tools or []):
            allowed_tools.extend(["Write", "Edit"])

        options_kwargs["allowed_tools"] = allowed_tools

        options = ClaudeAgentOptions(**options_kwargs)

        # Collect response
        full_response = ""
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "result"):
                full_response = message.result
            elif hasattr(message, "content"):
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        full_response += block.text

        # Try to parse as JSON
        try:
            # Strip markdown fences if present
            cleaned = full_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
                cleaned = cleaned.rsplit("```", 1)[0]
            return json.loads(cleaned)
        except (json.JSONDecodeError, IndexError):
            return {"summary": full_response, "actions": [], "raw": True}

    async def execute_with_anthropic_api(self, prompt: str, agent: AgentConfig) -> dict:
        """Fallback: execute directly via Anthropic Messages API."""
        import httpx

        headers = {"Content-Type": "application/json", "anthropic-version": "2023-06-01"}

        if settings.anthropic_api_key:
            headers["x-api-key"] = settings.anthropic_api_key

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json={
                        "model": agent.model or settings.default_model,
                        "max_tokens": 4096,
                        "system": (
                            f"You are {agent.name}. {agent.description}\n"
                            "Respond with valid JSON only: {{\"actions\": [...], \"summary\": \"...\"}}"
                        ),
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )

            if resp.status_code == 401:
                raise RuntimeError("LLM authentication failed. Check your ANTHROPIC_API_KEY.")
            if resp.status_code == 429:
                raise RuntimeError("LLM rate limit exceeded. Try again later or reduce agent frequency.")
            if resp.status_code == 529:
                raise RuntimeError("Anthropic API is overloaded. Try again in a few minutes.")
            if resp.status_code >= 500:
                raise RuntimeError(f"LLM provider error (HTTP {resp.status_code}). The API may be experiencing issues.")
            if resp.status_code >= 400:
                raise RuntimeError(f"LLM request failed (HTTP {resp.status_code}): {resp.text[:200]}")

            data = resp.json()
        except httpx.ConnectError:
            raise RuntimeError("Cannot connect to LLM provider. Check your network and API configuration.")
        except httpx.TimeoutException:
            raise RuntimeError("LLM request timed out. The model may be overloaded.")

        # Check for API-level errors
        if "error" in data:
            err_msg = data["error"].get("message", str(data["error"]))
            raise RuntimeError(f"LLM API error: {err_msg}")

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        try:
            cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"summary": text, "actions": [], "raw": True}

    async def _execute_llm(self, prompt: str, agent: AgentConfig) -> dict:
        """Execute LLM call with provider fallback, retry, and timeout enforcement."""
        timeout_seconds = (agent.config or {}).get("timeout_seconds", 300)
        max_retries = 3
        base_delay = 2.0

        async def _run():
            provider = settings.llm_provider
            if provider in (LLMProvider.ANTHROPIC_API, LLMProvider.ANTHROPIC_OAUTH):
                try:
                    return await self.execute_with_agent_sdk(prompt, agent)
                except Exception as sdk_err:
                    logger.warning(f"Agent SDK failed, falling back to API: {sdk_err}")
                    return await self.execute_with_anthropic_api(prompt, agent)
            else:
                return await self.execute_with_anthropic_api(prompt, agent)

        last_error = None
        for attempt in range(max_retries):
            try:
                return await asyncio.wait_for(_run(), timeout=timeout_seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Agent {agent.name} timed out after {timeout_seconds}s. "
                    f"Increase timeout_seconds in agent config if needed."
                )
            except RuntimeError as e:
                err_msg = str(e)
                # Retry on rate limits and server errors
                if any(keyword in err_msg for keyword in ["rate limit", "overloaded", "HTTP 5", "HTTP 429"]):
                    last_error = e
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        f"Agent {agent.name} attempt {attempt + 1}/{max_retries} failed: {err_msg}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_error or RuntimeError(f"Agent {agent.name} failed after {max_retries} retries")

    async def start_run(self, agent: AgentConfig, trigger: str, db: AsyncSession) -> AgentRun:
        """Start an agent run - creates log entry, executes, writes results."""

        # Create run record
        run = AgentRun(agent_id=agent.id, trigger=trigger, status=AgentRunStatus.RUNNING)
        db.add(run)
        agent.status = AgentStatus.RUNNING
        await db.flush()

        # Broadcast status
        await broadcast("agent.started", {"agent_id": str(agent.id), "run_id": str(run.id)})

        try:
            # Build context and render prompt
            context = await self.build_context(agent, db)
            prompt = self.render_prompt(agent.prompt_template, context)
            run.input_data = {"prompt_length": len(prompt), "context_keys": list(context.keys())}

            # Execute with timeout enforcement and retry
            result = await self._execute_llm(prompt, agent)

            # Validate output
            validated, validation_warnings = validate_agent_output(result)
            if validation_warnings:
                logger.warning(
                    f"Agent {agent.name} output validation warnings: {validation_warnings}"
                )
                result["_validation_warnings"] = validation_warnings

            # Update run
            run.status = AgentRunStatus.COMPLETED
            run.output_data = result
            run.completed_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.IDLE
            agent.last_run_at = datetime.now(timezone.utc)

            # Check if agent requires approval — use validated actions
            requires_approval = agent.config.get("requires_approval", False) if agent.config else False
            actions = [a.model_dump(exclude_none=True) for a in validated.actions]

            if requires_approval and actions:
                # Queue for approval instead of executing immediately
                from datetime import timedelta
                approval = AgentApproval(
                    run_id=run.id,
                    agent_id=agent.id,
                    actions=actions,
                    summary=result.get("summary", ""),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
                )
                db.add(approval)
                await broadcast("approval.pending", {
                    "agent_id": str(agent.id),
                    "run_id": str(run.id),
                    "action_count": len(actions),
                    "summary": result.get("summary", ""),
                })
            else:
                await self._process_actions(actions, agent, db)

            await broadcast("agent.completed", {
                "agent_id": str(agent.id),
                "run_id": str(run.id),
                "summary": result.get("summary", ""),
            })

            # Create notification
            try:
                from app.api.notifications import create_notification
                summary = result.get("summary", "Run completed")
                category = "approval" if requires_approval and actions else "success"
                await create_notification(
                    db, title=f"{agent.name} completed",
                    body=summary[:200], category=category,
                    source=f"agent:{agent.slug}",
                )
            except Exception:
                pass  # notifications are best-effort

            # Agent chaining: if this agent has a "chain_to" config, trigger the next agent
            chain_to = agent.config.get("chain_to") if agent.config else None
            if chain_to:
                try:
                    from sqlalchemy import select as sa_select
                    chain_result = await db.execute(
                        sa_select(AgentConfig).where(AgentConfig.slug == chain_to)
                    )
                    next_agent = chain_result.scalar_one_or_none()
                    if next_agent and next_agent.status != AgentStatus.RUNNING:
                        logger.info(f"Chaining: {agent.name} -> {next_agent.name}")
                        asyncio.create_task(self._chain_run(next_agent.id, result, trigger))
                except Exception as chain_err:
                    logger.warning(f"Agent chaining failed: {chain_err}")

        except Exception as e:
            run.status = AgentRunStatus.FAILED
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.ERROR
            logger.error(f"Agent {agent.name} run failed: {e}")

            await broadcast("agent.failed", {
                "agent_id": str(agent.id),
                "run_id": str(run.id),
                "error": str(e),
            })

            # Notification for failures
            try:
                from app.api.notifications import create_notification
                await create_notification(
                    db, title=f"{agent.name} failed",
                    body=str(e)[:200], category="error",
                    source=f"agent:{agent.slug}",
                )
            except Exception:
                pass

        await db.flush()

        # Log event
        event = EventLog(
            event_type=f"agent.run.{run.status.value}",
            entity_type="agent",
            entity_id=agent.id,
            source=f"agent:{agent.slug}",
            data={"run_id": str(run.id), "trigger": trigger},
        )
        db.add(event)
        await db.flush()

        return run

    async def _chain_run(self, next_agent_id, previous_result: dict, trigger: str):
        """Run the next agent in a chain, passing previous output as context."""
        from app.db.session import async_session
        async with async_session() as db:
            next_agent = await db.get(AgentConfig, next_agent_id)
            if not next_agent or next_agent.status == AgentStatus.RUNNING:
                return
            # Store chain input as agent memory (transient, not in config)
            from app.db.models import AgentMemory
            existing = await db.execute(
                select(AgentMemory).where(
                    AgentMemory.agent_id == next_agent.id,
                    AgentMemory.key == "_chain_input",
                )
            )
            mem = existing.scalar_one_or_none()
            chain_data = json.dumps(previous_result)[:2000]  # limit size
            if mem:
                mem.value = chain_data
            else:
                db.add(AgentMemory(
                    agent_id=next_agent.id, key="_chain_input",
                    value=chain_data, memory_type="chain",
                ))
            await self.start_run(next_agent, trigger=f"chain:{trigger}", db=db)
            await db.commit()

    async def _process_actions(self, actions: list, agent: AgentConfig, db: AsyncSession):
        """Process structured actions from agent output and write to DB."""
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
                await broadcast("task.created", {"text": task.text, "source": task.source})

            elif action_type == "create_idea" and "ideas" in (agent.data_writes or []):
                idea = Idea(
                    text=action.get("text", ""),
                    tags=action.get("tags", []),
                    source=f"agent:{agent.slug}",
                )
                db.add(idea)
                await broadcast("idea.created", {"text": idea.text, "source": idea.source})

            elif action_type == "update_task" and "tasks" in (agent.data_writes or []):
                task_id = action.get("task_id")
                if task_id:
                    task = await db.get(Task, UUID(task_id))
                    if task:
                        if "status" in action:
                            task.status = action["status"]
                        if "priority" in action:
                            task.priority = action["priority"]

            elif action_type == "add_reading" and "reading" in (agent.data_writes or []):
                item = ReadingItem(
                    title=action.get("title", ""),
                    url=action.get("url"),
                    source=f"agent:{agent.slug}",
                    tags=action.get("tags", []),
                )
                db.add(item)

            elif action_type == "create_journal" and "journal" in (agent.data_writes or []):
                from app.db.models import MoodLevel
                mood_str = action.get("mood")
                mood = MoodLevel(mood_str) if mood_str and mood_str in MoodLevel.__members__.values() else None
                entry = JournalEntry(
                    content=action.get("content", ""),
                    mood=mood,
                    energy=action.get("energy"),
                    tags=action.get("tags", []),
                    wins=action.get("wins", []),
                    challenges=action.get("challenges", []),
                    gratitude=action.get("gratitude", []),
                    source=f"agent:{agent.slug}",
                )
                db.add(entry)
                await broadcast("journal.created", {"source": f"agent:{agent.slug}"})

            elif action_type == "save_memory":
                # Agents can persist memory entries for future runs
                key = action.get("key")
                value = action.get("value")
                if key and value:
                    existing = await db.execute(
                        select(AgentMemory).where(
                            AgentMemory.agent_id == agent.id,
                            AgentMemory.key == key,
                        )
                    )
                    mem = existing.scalar_one_or_none()
                    if mem:
                        mem.value = str(value)
                    else:
                        db.add(AgentMemory(
                            agent_id=agent.id, key=key, value=str(value),
                            memory_type=action.get("memory_type", "general"),
                        ))

            elif action_type == "create_goal" and "goals" in (agent.data_writes or []):
                goal = Goal(
                    title=action.get("title", "Untitled goal"),
                    description=action.get("description", ""),
                    project_id=agent.project_id,
                    tags=action.get("tags", []),
                )
                db.add(goal)
                await broadcast("goal.created", {"title": goal.title})

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
                db.add(EventLog(
                    event_type="signal.created", entity_type="signal",
                    entity_id=signal.id, source=f"agent:{agent.slug}",
                    data={"title": signal.title, "signal_type": signal.signal_type},
                ))
                await broadcast("signal.created", {"id": str(signal.id), "title": signal.title, "source": signal.source})

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
                db.add(EventLog(
                    event_type="content.created", entity_type="content",
                    entity_id=content.id, source=f"agent:{agent.slug}",
                    data={"title": content.title, "channel": content.channel},
                ))
                await broadcast("content.created", {"id": str(content.id), "title": content.title, "source": content.source})
