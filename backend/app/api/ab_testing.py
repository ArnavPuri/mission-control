"""A/B Testing for Agent Prompts.

Compare prompt variants by running the same agent with different prompts
and tracking which variant produces better results.
"""

import logging
import random
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentConfig, AgentRun, AgentRunStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class PromptVariant(BaseModel):
    name: str  # e.g. "control", "variant_a"
    prompt_template: str
    weight: float = 0.5  # traffic allocation


class ABTestCreate(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    variants: list[PromptVariant]


class ABTestUpdate(BaseModel):
    is_active: bool | None = None
    winner: str | None = None  # variant name to lock in as winner


# --- Endpoints ---

@router.get("")
async def list_ab_tests(db: AsyncSession = Depends(get_db)):
    """List all A/B tests across agents."""
    result = await db.execute(select(AgentConfig))
    agents = result.scalars().all()

    tests = []
    for agent in agents:
        config = agent.config or {}
        ab_tests = config.get("_ab_tests", [])
        for test in ab_tests:
            tests.append({
                "agent_id": str(agent.id),
                "agent_name": agent.name,
                **test,
            })
    return tests


@router.post("")
async def create_ab_test(data: ABTestCreate, db: AsyncSession = Depends(get_db)):
    """Create an A/B test for an agent's prompt.

    Variants are stored in the agent's config and randomly selected on each run.
    """
    agent = await db.get(AgentConfig, UUID(data.agent_id))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if len(data.variants) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 variants")

    # Normalize weights
    total_weight = sum(v.weight for v in data.variants)
    variants = [
        {
            "name": v.name,
            "prompt_template": v.prompt_template,
            "weight": v.weight / total_weight,
            "runs": 0,
            "successes": 0,
            "total_score": 0.0,
        }
        for v in data.variants
    ]

    test_entry = {
        "name": data.name,
        "description": data.description,
        "is_active": True,
        "winner": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "variants": variants,
    }

    config = dict(agent.config or {})
    ab_tests = config.get("_ab_tests", [])
    ab_tests.append(test_entry)
    config["_ab_tests"] = ab_tests
    agent.config = config
    await db.flush()

    return {
        "created": True,
        "agent_name": agent.name,
        "test_name": data.name,
        "variant_count": len(variants),
    }


@router.get("/{agent_id}/results")
async def get_test_results(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get A/B test results for an agent with statistical comparison."""
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    config = agent.config or {}
    ab_tests = config.get("_ab_tests", [])

    results = []
    for test in ab_tests:
        variant_results = []
        for v in test.get("variants", []):
            runs = v.get("runs", 0)
            successes = v.get("successes", 0)
            total_score = v.get("total_score", 0.0)
            variant_results.append({
                "name": v["name"],
                "runs": runs,
                "success_rate": round(successes / runs, 3) if runs > 0 else 0,
                "avg_score": round(total_score / runs, 3) if runs > 0 else 0,
                "weight": v.get("weight", 0.5),
            })

        # Determine leader
        leader = None
        if variant_results:
            by_score = sorted(variant_results, key=lambda x: x["avg_score"], reverse=True)
            if by_score[0]["runs"] >= 5:
                leader = by_score[0]["name"]

        results.append({
            "name": test["name"],
            "description": test.get("description", ""),
            "is_active": test.get("is_active", True),
            "winner": test.get("winner"),
            "suggested_leader": leader,
            "variants": variant_results,
            "created_at": test.get("created_at"),
        })

    return {"agent_id": str(agent.id), "agent_name": agent.name, "tests": results}


@router.patch("/{agent_id}/tests/{test_name}")
async def update_ab_test(
    agent_id: UUID,
    test_name: str,
    data: ABTestUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an A/B test (activate/deactivate, declare winner).

    When a winner is declared, the agent's prompt_template is updated
    to the winning variant and the test is marked inactive.
    """
    agent = await db.get(AgentConfig, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    config = dict(agent.config or {})
    ab_tests = config.get("_ab_tests", [])

    test = None
    for t in ab_tests:
        if t["name"] == test_name:
            test = t
            break

    if not test:
        raise HTTPException(status_code=404, detail=f"Test '{test_name}' not found")

    if data.is_active is not None:
        test["is_active"] = data.is_active

    if data.winner:
        # Find winning variant and apply its prompt
        for v in test.get("variants", []):
            if v["name"] == data.winner:
                agent.prompt_template = v["prompt_template"]
                test["winner"] = data.winner
                test["is_active"] = False
                test["resolved_at"] = datetime.now(timezone.utc).isoformat()
                break
        else:
            raise HTTPException(status_code=400, detail=f"Variant '{data.winner}' not found")

    config["_ab_tests"] = ab_tests
    agent.config = config
    await db.flush()

    return {"updated": True, "test_name": test_name, "winner": test.get("winner")}


# --- Helper for runner integration ---

def select_variant(agent: AgentConfig) -> tuple[str | None, str | None]:
    """Select a prompt variant for the current run based on A/B test weights.

    Returns (prompt_template, variant_name) or (None, None) if no active test.
    Called by the agent runner before execution.
    """
    config = agent.config or {}
    ab_tests = config.get("_ab_tests", [])

    for test in ab_tests:
        if not test.get("is_active", False):
            continue

        variants = test.get("variants", [])
        if not variants:
            continue

        # Weighted random selection
        weights = [v.get("weight", 0.5) for v in variants]
        selected = random.choices(variants, weights=weights, k=1)[0]
        return selected["prompt_template"], selected["name"]

    return None, None


def record_variant_result(agent: AgentConfig, variant_name: str, success: bool, score: float = 0.0):
    """Record the result of running a variant.

    Called by the agent runner after execution.
    """
    config = agent.config or {}
    ab_tests = config.get("_ab_tests", [])

    for test in ab_tests:
        if not test.get("is_active", False):
            continue
        for v in test.get("variants", []):
            if v["name"] == variant_name:
                v["runs"] = v.get("runs", 0) + 1
                if success:
                    v["successes"] = v.get("successes", 0) + 1
                v["total_score"] = v.get("total_score", 0.0) + score
                break

    config["_ab_tests"] = ab_tests
    agent.config = config
