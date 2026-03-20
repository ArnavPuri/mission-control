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
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, LLMProvider
from app.db.models import (
    AgentConfig, AgentRun, AgentStatus, AgentRunStatus,
    Project, Task, Idea, EventLog, TaskStatus,
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
        """Build a rich system prompt combining agent persona, user identity, and output format."""
        # Agent persona (from YAML config)
        persona = (agent.config or {}).get("persona", "")
        tone = (agent.config or {}).get("tone", "")

        parts = []

        # 1. Identity line
        if persona:
            parts.append(f"You are {agent.name} — {persona}.")
        else:
            parts.append(f"You are {agent.name}, a specialized AI agent.")

        # 2. Role description
        if agent.description:
            parts.append(f"Role: {agent.description}")

        # 3. Tone directive
        if tone:
            parts.append(f"Tone: {tone}.")

        # 4. User identity context (from workspace/identity.md)
        identity = settings.identity
        if identity:
            parts.append(f"\n## About the User\n{identity}")

        # 5. Time awareness
        parts.append(
            "\n## Time Awareness\n"
            'Your context includes "time_context" with the current UTC time, period (morning/afternoon/evening/night), '
            "and guidance on what kind of work is appropriate. Adapt your behavior accordingly:\n"
            "- Morning: planning, prioritization, daily briefings\n"
            "- Afternoon: execution, progress updates\n"
            "- Evening: reflection, reviews, day summaries\n"
            "- Night: quiet background tasks, prep for tomorrow"
        )

        # 6. Memory & learning instructions
        parts.append(
            "\n## Memory & Learning\n"
            "You have persistent memory that survives between runs. Use it.\n"
            '- Your context includes "past_runs" showing your last 5 runs (summaries, actions, dates).\n'
            '- Your "memory" dict contains things you saved previously. Reference it.\n'
            '- Your "shared_memory" dict contains notes from other agents. Read it for cross-agent context.\n'
            "- To remember something for next time, include a save_memory action.\n"
            "- To share context with other agents, include a save_shared_memory action.\n"
            "- Avoid repeating the same actions from recent runs. Check past_runs first.\n"
            "- If you notice a pattern (e.g., you keep creating similar tasks), save an insight to memory."
        )

        # 7. Output format
        parts.append(
            "\n## Output Format\n"
            "You MUST respond with valid JSON only. No markdown, no explanation.\n"
            'Your output should contain a "summary" string and an "actions" array.'
        )

        return "\n".join(parts)

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

        # Standup context: load all agents' status and recent activity for coordination
        if "standup" in (agent.data_reads or []):
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=36)

            # All agents and their current status
            all_agents_result = await db.execute(
                select(AgentConfig).where(AgentConfig.status != AgentStatus.DISABLED)
            )
            all_agents = all_agents_result.scalars().all()

            standup_roster = []
            for a in all_agents:
                if a.id == agent.id:
                    continue  # skip self

                agent_info = {
                    "name": a.name,
                    "slug": a.slug,
                    "description": a.description,
                    "status": a.status.value,
                    "model": a.model,
                    "schedule": f"{a.schedule_type}:{a.schedule_value}" if a.schedule_type else "manual",
                    "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
                }

                # Last completed run (within 36h window)
                last_run_result = await db.execute(
                    select(AgentRun)
                    .where(
                        AgentRun.agent_id == a.id,
                        AgentRun.status == AgentRunStatus.COMPLETED,
                        AgentRun.completed_at >= cutoff,
                    )
                    .order_by(AgentRun.completed_at.desc())
                    .limit(1)
                )
                last_run = last_run_result.scalar_one_or_none()
                if last_run:
                    agent_info["last_run"] = {
                        "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
                        "summary": (last_run.output_data or {}).get("summary", "")[:300],
                        "action_count": len((last_run.output_data or {}).get("actions", [])),
                        "action_types": list(set(
                            act.get("type", "") for act in (last_run.output_data or {}).get("actions", [])
                            if isinstance(act, dict)
                        )),
                    }

                # Last failed run (within 36h) — surface errors
                failed_result = await db.execute(
                    select(AgentRun)
                    .where(
                        AgentRun.agent_id == a.id,
                        AgentRun.status == AgentRunStatus.FAILED,
                        AgentRun.completed_at >= cutoff,
                    )
                    .order_by(AgentRun.completed_at.desc())
                    .limit(1)
                )
                failed_run = failed_result.scalar_one_or_none()
                if failed_run:
                    agent_info["last_failure"] = {
                        "completed_at": failed_run.completed_at.isoformat() if failed_run.completed_at else None,
                        "error": (failed_run.error or "")[:200],
                    }

                # Agent's own memory (key insights it has saved)
                mem_result = await db.execute(
                    select(AgentMemory)
                    .where(
                        AgentMemory.agent_id == a.id,
                        AgentMemory.memory_type != "system",
                    )
                    .order_by(AgentMemory.updated_at.desc())
                    .limit(5)
                )
                agent_memories = mem_result.scalars().all()
                if agent_memories:
                    agent_info["memories"] = {m.key: m.value[:200] for m in agent_memories}

                standup_roster.append(agent_info)

            context["standup"] = standup_roster

        # Time-based context: tell agent what time of day it is for appropriate behavior
        now = datetime.now(timezone.utc)
        hour = now.hour
        if hour < 6:
            time_period = "late_night"
            time_guidance = "It's late night. Focus on low-priority background tasks. Avoid user-facing notifications."
        elif hour < 12:
            time_period = "morning"
            time_guidance = "It's morning. Good time for planning, prioritization, and daily briefings."
        elif hour < 17:
            time_period = "afternoon"
            time_guidance = "It's afternoon. Focus on execution, progress updates, and unblocking tasks."
        elif hour < 21:
            time_period = "evening"
            time_guidance = "It's evening. Good time for reflection, reviews, and summarizing the day."
        else:
            time_period = "night"
            time_guidance = "It's night. Focus on quiet background tasks and preparation for tomorrow."

        context["time_context"] = {
            "utc_time": now.isoformat(),
            "hour": hour,
            "period": time_period,
            "day_of_week": now.strftime("%A").lower(),
            "guidance": time_guidance,
        }

        # Load agent memory (persistent context from previous runs)
        mem_result = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id == agent.id).order_by(AgentMemory.updated_at.desc())
        )
        memories = mem_result.scalars().all()
        if memories:
            context["memory"] = {m.key: m.value for m in memories}

        # Load shared scratchpad (agent_id=NULL, visible to all agents)
        shared_result = await db.execute(
            select(AgentMemory).where(AgentMemory.agent_id.is_(None)).order_by(AgentMemory.updated_at.desc())
        )
        shared_memories = shared_result.scalars().all()
        if shared_memories:
            context["shared_memory"] = {m.key: m.value for m in shared_memories}

        # Load run history (last 5 completed runs for self-awareness)
        run_history = await db.execute(
            select(AgentRun)
            .where(
                AgentRun.agent_id == agent.id,
                AgentRun.status == AgentRunStatus.COMPLETED,
            )
            .order_by(AgentRun.completed_at.desc())
            .limit(5)
        )
        past_runs = run_history.scalars().all()
        if past_runs:
            context["past_runs"] = [
                {
                    "run_date": r.completed_at.isoformat() if r.completed_at else None,
                    "trigger": r.trigger,
                    "summary": (r.output_data or {}).get("summary", "")[:300],
                    "action_count": len((r.output_data or {}).get("actions", [])),
                    "action_types": list(set(
                        a.get("type", "") for a in (r.output_data or {}).get("actions", [])
                        if isinstance(a, dict)
                    )),
                }
                for r in past_runs
            ]

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

        # Brand profile for marketing agents
        if any(r in (agent.data_reads or []) for r in ("marketing_signals", "marketing_content")):
            from app.db.models import BrandProfile
            bp_result = await db.execute(select(BrandProfile).limit(1))
            bp = bp_result.scalar_one_or_none()
            if bp:
                context["brand"] = {
                    "name": bp.name,
                    "tone": bp.tone,
                    "topics": bp.topics or [],
                    "talking_points": bp.talking_points or {},
                    "avoid": bp.avoid or [],
                    "example_posts": bp.example_posts or [],
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
        import os

        # Build options
        options_kwargs = {
            "system_prompt": self._build_system_prompt(agent),
            "max_turns": 10,
            "setting_sources": ["project", "user"],
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

        # Ensure auth env vars and CLI path are available to the SDK subprocess
        import shutil
        env = dict(os.environ)
        if settings.anthropic_api_key:
            env["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
        if settings.claude_code_oauth_token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = settings.claude_code_oauth_token
        options_kwargs["env"] = env

        # Explicitly resolve claude CLI path so SDK finds it regardless of how uvicorn was started
        cli_path = shutil.which("claude")
        if cli_path:
            options_kwargs["cli_path"] = cli_path

        # Session resumption
        if agent.session_id and agent.session_expires_at and agent.session_expires_at > datetime.now(timezone.utc):
            options_kwargs["resume"] = agent.session_id
            if agent.last_message_uuid:
                options_kwargs["resume_session_at"] = agent.last_message_uuid
            logger.info(f"Resuming session {agent.session_id[:12]}... for {agent.name}")

        options = ClaudeAgentOptions(**options_kwargs)

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
                    # Track last assistant message UUID for session resumption
                    if role == "assistant":
                        for attr in ('uuid', 'id', 'message_id'):
                            if hasattr(message, attr):
                                last_assistant_uuid = getattr(message, attr)
                                break

        # Store session info and transcript for the caller to save
        self._last_session_id = new_session_id
        self._last_message_uuid = last_assistant_uuid
        self._last_transcript = transcript if transcript else None

        if not full_response:
            return {"summary": "Agent produced no output", "actions": [], "raw": True}

        # Try to parse as JSON
        try:
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

        if not settings.anthropic_api_key:
            raise RuntimeError(
                "Direct API fallback requires ANTHROPIC_API_KEY. "
                "OAuth tokens only work with the Agent SDK."
            )

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": settings.anthropic_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json={
                        "model": agent.model or settings.default_model,
                        "max_tokens": 4096,
                        "system": self._build_system_prompt(agent),
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

    async def _self_evaluate(self, result: dict, agent: AgentConfig, min_confidence: float) -> tuple[dict, dict | None]:
        """Score agent output quality. If below threshold, retry once with feedback.

        Returns (possibly_improved_result, evaluation_metadata).
        """
        summary = result.get("summary", "")
        actions = result.get("actions", [])

        # Simple heuristic scoring (no LLM call needed)
        score = 0.5  # baseline
        reasons = []

        # Penalize empty or very short summary
        if not summary or len(summary) < 10:
            score -= 0.3
            reasons.append("Summary too short or missing")
        elif len(summary) > 50:
            score += 0.1
            reasons.append("Good summary length")

        # Penalize no actions when agent has data_writes
        if not actions and (agent.data_writes or []):
            score -= 0.2
            reasons.append("No actions produced despite write permissions")
        elif actions:
            score += 0.1
            reasons.append(f"{len(actions)} actions produced")

        # Penalize if raw/unparsed output
        if result.get("raw"):
            score -= 0.3
            reasons.append("Output was not valid JSON")

        # Reward valid action types
        valid_types = {"create_task", "create_idea", "update_task", "add_reading",
                       "create_journal", "save_memory", "save_shared_memory",
                       "create_goal", "create_signal", "create_content"}
        for a in actions:
            if isinstance(a, dict) and a.get("type") in valid_types:
                score += 0.05

        score = max(0.0, min(1.0, score))
        eval_meta = {"score": round(score, 2), "reasons": reasons, "threshold": min_confidence}

        if score < min_confidence:
            # Retry once with feedback
            logger.info(
                f"Agent {agent.name} self-eval score {score:.2f} < {min_confidence}. Retrying with feedback."
            )
            eval_meta["retried"] = True
            feedback_prompt = (
                f"Your previous output scored {score:.2f} (threshold: {min_confidence}).\n"
                f"Issues: {'; '.join(reasons)}\n"
                f"Previous summary: {summary[:200]}\n\n"
                "Please try again with a better response. "
                "Ensure you provide a clear summary and well-formed actions as JSON."
            )
            try:
                retry_result = await self._execute_llm(feedback_prompt, agent)
                # Re-score
                retry_summary = retry_result.get("summary", "")
                retry_actions = retry_result.get("actions", [])
                retry_score = 0.5
                if retry_summary and len(retry_summary) > 10:
                    retry_score += 0.2
                if retry_actions:
                    retry_score += 0.15
                if not retry_result.get("raw"):
                    retry_score += 0.15
                retry_score = min(1.0, retry_score)
                eval_meta["retry_score"] = round(retry_score, 2)

                if retry_score > score:
                    return retry_result, eval_meta
            except Exception as e:
                logger.warning(f"Self-eval retry failed for {agent.name}: {e}")
                eval_meta["retry_error"] = str(e)[:100]

        return result, eval_meta

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
                    logger.error(f"Agent SDK failed: {type(sdk_err).__name__}: {sdk_err}", exc_info=True)
                    if provider == LLMProvider.ANTHROPIC_OAUTH:
                        # No point falling back to raw API — OAuth tokens don't work there
                        raise RuntimeError(f"Agent SDK failed and no API key fallback available: {sdk_err}") from sdk_err
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

        # Budget check before running
        from app.api.agent_budget import check_budget_before_run
        budget_ok, budget_msg = await check_budget_before_run(agent, db)
        if not budget_ok:
            run = AgentRun(
                agent_id=agent.id, trigger=trigger, status=AgentRunStatus.FAILED,
                error=budget_msg, completed_at=datetime.now(timezone.utc),
            )
            db.add(run)
            await db.flush()
            logger.warning(f"Agent {agent.name} blocked by budget: {budget_msg}")
            await broadcast("agent.budget_exceeded", {
                "agent_id": str(agent.id), "message": budget_msg,
            })
            return run

        # Create run record
        run = AgentRun(agent_id=agent.id, trigger=trigger, status=AgentRunStatus.RUNNING)
        db.add(run)
        agent.status = AgentStatus.RUNNING
        await db.flush()

        # Broadcast status
        await broadcast("agent.started", {"agent_id": str(agent.id), "run_id": str(run.id)})

        # A/B test: select prompt variant if active test exists
        ab_variant_name = None
        try:
            from app.api.ab_testing import select_variant, record_variant_result
            variant_prompt, ab_variant_name = select_variant(agent)
        except Exception:
            variant_prompt = None

        try:
            # Build context and render prompt
            context = await self.build_context(agent, db)
            template = variant_prompt or agent.prompt_template
            prompt = self.render_prompt(template, context)
            run.input_data = {
                "prompt_length": len(prompt),
                "context_keys": list(context.keys()),
                "ab_variant": ab_variant_name,
            }

            # Execute with timeout enforcement and retry
            result = await self._execute_llm(prompt, agent)

            # Self-evaluation: score output quality and retry if low confidence
            self_eval_enabled = (agent.config or {}).get("self_eval", False)
            min_confidence = (agent.config or {}).get("min_confidence", 0.5)
            if self_eval_enabled:
                result, eval_meta = await self._self_evaluate(result, agent, min_confidence)
                if eval_meta:
                    result["_self_eval"] = eval_meta

            # Validate output
            validated, validation_warnings = validate_agent_output(result)
            if validation_warnings:
                logger.warning(
                    f"Agent {agent.name} output validation warnings: {validation_warnings}"
                )
                result["_validation_warnings"] = validation_warnings

            # Record A/B test result
            if ab_variant_name:
                try:
                    eval_score = result.get("_self_eval", {}).get("score", 0.5)
                    record_variant_result(agent, ab_variant_name, True, eval_score)
                except Exception:
                    pass

            # Update run
            run.status = AgentRunStatus.COMPLETED
            run.output_data = result
            run.completed_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.IDLE
            agent.last_run_at = datetime.now(timezone.utc)

            # Save transcript
            run.transcript = self._last_transcript

            # Update session persistence
            if agent.session_window_days and agent.session_window_days > 0:
                if self._last_session_id:
                    agent.session_id = self._last_session_id
                if self._last_message_uuid:
                    agent.last_message_uuid = self._last_message_uuid
                agent.session_expires_at = datetime.now(timezone.utc) + timedelta(days=agent.session_window_days)

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

            # Create notification (respects user preferences)
            try:
                from app.api.notifications import create_notification
                from app.api.brand import get_notification_prefs_dict
                notif_prefs = await get_notification_prefs_dict(db)
                summary = result.get("summary", "Run completed")
                category = "approval" if requires_approval and actions else "success"
                if notif_prefs.get("agent_completions", True):
                    await create_notification(
                        db, title=f"{agent.name} completed",
                        body=summary[:200], category=category,
                        source=f"agent:{agent.slug}",
                        priority="routine",
                    )
            except Exception:
                pass  # notifications are best-effort

            # Post-run learning: extract and persist run insights to agent memory
            await self._post_run_learn(agent, run, result, db)

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
            run.transcript = self._last_transcript
            run.completed_at = datetime.now(timezone.utc)
            agent.status = AgentStatus.ERROR
            logger.error(f"Agent {agent.name} run failed: {e}")

            await broadcast("agent.failed", {
                "agent_id": str(agent.id),
                "run_id": str(run.id),
                "error": str(e),
            })

            # Notification for failures (respects user preferences)
            try:
                from app.api.notifications import create_notification
                from app.api.brand import get_notification_prefs_dict
                notif_prefs = await get_notification_prefs_dict(db)
                if notif_prefs.get("agent_failures", True):
                    await create_notification(
                        db, title=f"{agent.name} failed",
                        body=str(e)[:200], category="error",
                        source=f"agent:{agent.slug}",
                        priority="urgent",
                    )
            except Exception:
                pass

        await db.flush()

        # Reset per-run state
        self._last_session_id = None
        self._last_message_uuid = None
        self._last_transcript = None

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

    async def _post_run_learn(self, agent: AgentConfig, run: AgentRun, result: dict, db: AsyncSession):
        """Extract insights from a completed run and persist to agent memory.

        Tracks: run count, last summary, action patterns, and running stats.
        This gives agents self-awareness of their own performance over time.
        """
        try:
            actions = result.get("actions", [])
            action_types = [a.get("type", "") for a in actions if isinstance(a, dict)]

            # 1. Increment run counter
            counter_result = await db.execute(
                select(AgentMemory).where(
                    AgentMemory.agent_id == agent.id,
                    AgentMemory.key == "_run_count",
                )
            )
            counter = counter_result.scalar_one_or_none()
            run_count = int(counter.value) + 1 if counter else 1
            if counter:
                counter.value = str(run_count)
            else:
                db.add(AgentMemory(
                    agent_id=agent.id, key="_run_count",
                    value=str(run_count), memory_type="system",
                ))

            # 2. Save last run summary for quick recall
            last_summary = result.get("summary", "")[:500]
            if last_summary:
                existing = await db.execute(
                    select(AgentMemory).where(
                        AgentMemory.agent_id == agent.id,
                        AgentMemory.key == "_last_run_summary",
                    )
                )
                mem = existing.scalar_one_or_none()
                if mem:
                    mem.value = last_summary
                else:
                    db.add(AgentMemory(
                        agent_id=agent.id, key="_last_run_summary",
                        value=last_summary, memory_type="system",
                    ))

            # 3. Track action pattern stats (what action types this agent typically produces)
            if action_types:
                stats_result = await db.execute(
                    select(AgentMemory).where(
                        AgentMemory.agent_id == agent.id,
                        AgentMemory.key == "_action_stats",
                    )
                )
                stats_mem = stats_result.scalar_one_or_none()
                try:
                    stats = json.loads(stats_mem.value) if stats_mem else {}
                except (json.JSONDecodeError, AttributeError):
                    stats = {}

                for at in action_types:
                    stats[at] = stats.get(at, 0) + 1
                stats["_total_actions"] = stats.get("_total_actions", 0) + len(action_types)
                stats["_total_runs"] = run_count

                stats_json = json.dumps(stats)
                if stats_mem:
                    stats_mem.value = stats_json
                else:
                    db.add(AgentMemory(
                        agent_id=agent.id, key="_action_stats",
                        value=stats_json, memory_type="system",
                    ))

            await db.flush()
        except Exception as e:
            logger.debug(f"Post-run learning failed for {agent.name}: {e}")

    async def _fire_trigger(self, entity_type: str, event: str, entity_data: dict, db: AsyncSession):
        """Fire event-driven triggers (best-effort)."""
        try:
            from app.api.triggers import evaluate_triggers
            await evaluate_triggers(entity_type, event, entity_data, db)
        except Exception as e:
            logger.debug(f"Trigger evaluation failed: {e}")

    async def _process_actions(self, actions: list, agent: AgentConfig, db: AsyncSession):
        """Process structured actions from agent output and write to DB."""
        # Track counts for batched summary notification
        _signal_count = 0
        _signal_high_count = 0
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
                await self._fire_trigger("task", "created", {
                    "text": task.text, "priority": task.priority.value if hasattr(task.priority, 'value') else task.priority,
                    "status": task.status.value if hasattr(task.status, 'value') else task.status,
                    "tags": task.tags or [], "source": task.source,
                }, db)

            elif action_type == "create_idea" and "ideas" in (agent.data_writes or []):
                idea = Idea(
                    text=action.get("text", ""),
                    tags=action.get("tags", []),
                    source=f"agent:{agent.slug}",
                )
                db.add(idea)
                await db.flush()
                await broadcast("idea.created", {"text": idea.text, "source": idea.source})
                await self._fire_trigger("idea", "created", {
                    "text": idea.text, "tags": idea.tags or [], "source": idea.source,
                }, db)

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
                await db.flush()
                await broadcast("journal.created", {"source": f"agent:{agent.slug}"})
                await self._fire_trigger("journal", "created", {
                    "content": entry.content[:200], "mood": mood_str,
                    "energy": entry.energy, "tags": entry.tags or [], "source": entry.source,
                }, db)

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

            elif action_type == "save_shared_memory":
                # Write to shared scratchpad (agent_id=NULL, visible to all agents)
                key = action.get("key")
                value = action.get("value")
                if key and value:
                    existing = await db.execute(
                        select(AgentMemory).where(
                            AgentMemory.agent_id.is_(None),
                            AgentMemory.key == key,
                        )
                    )
                    mem = existing.scalar_one_or_none()
                    if mem:
                        mem.value = str(value)
                    else:
                        db.add(AgentMemory(
                            agent_id=None, key=key, value=str(value),
                            memory_type="shared",
                        ))

            elif action_type == "create_goal" and "goals" in (agent.data_writes or []):
                goal = Goal(
                    title=action.get("title", "Untitled goal"),
                    description=action.get("description", ""),
                    project_id=agent.project_id,
                    tags=action.get("tags", []),
                )
                db.add(goal)
                await db.flush()
                await broadcast("goal.created", {"title": goal.title})
                await self._fire_trigger("goal", "created", {
                    "title": goal.title, "description": goal.description, "tags": goal.tags or [],
                }, db)

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
                await self._fire_trigger("signal", "created", {
                    "title": signal.title, "source_type": signal.source_type,
                    "signal_type": signal.signal_type, "relevance_score": signal.relevance_score,
                    "tags": signal.tags or [], "source": signal.source,
                }, db)

                # Track for batched summary
                _signal_count += 1
                if action.get("relevance_score", 0.5) > 0.8:
                    _signal_high_count += 1

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
                await self._fire_trigger("content", "created", {
                    "title": content.title, "channel": content.channel,
                    "tags": content.tags or [], "source": content.source,
                }, db)

                # Track for batched summary
                _content_count += 1

        # --- Batched summary notifications (after all actions processed) ---
        from app.api.brand import get_notification_prefs_dict
        prefs = await get_notification_prefs_dict(db)

        if _signal_count > 0 and prefs.get("signal_summary", True):
            high_part = f", {_signal_high_count} high relevance" if _signal_high_count else ""
            await create_notification(
                db,
                title=f"Found {_signal_count} new leads{high_part}",
                category="signal",
                source=f"agent:{agent.slug}",
                data={"signal_count": _signal_count, "high_count": _signal_high_count},
                priority="urgent" if _signal_high_count > 0 else "routine",
            )

        if _content_count > 0 and prefs.get("content_drafts", True):
            await create_notification(
                db,
                title=f"{_content_count} new draft{'s' if _content_count > 1 else ''} ready for review",
                category="content",
                source=f"agent:{agent.slug}",
                priority="routine",
            )
