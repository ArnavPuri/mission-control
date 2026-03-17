from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import AgentApproval, ApprovalStatus, AgentConfig, AgentRun
from app.orchestrator.runner import AgentRunner
from app.api.ws import broadcast

router = APIRouter()


@router.get("")
async def list_pending_approvals(db: AsyncSession = Depends(get_db)):
    """List all pending agent approvals."""
    result = await db.execute(
        select(AgentApproval)
        .where(AgentApproval.status == ApprovalStatus.PENDING)
        .order_by(AgentApproval.created_at.desc())
    )
    approvals = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "agent_id": str(a.agent_id),
            "agent_name": a.agent.name if a.agent else "Unknown",
            "run_id": str(a.run_id),
            "summary": a.summary,
            "actions": a.actions,
            "action_count": len(a.actions) if isinstance(a.actions, list) else 0,
            "created_at": a.created_at.isoformat(),
            "expires_at": a.expires_at.isoformat() if a.expires_at else None,
        }
        for a in approvals
    ]


@router.post("/{approval_id}/approve")
async def approve_actions(approval_id: UUID, db: AsyncSession = Depends(get_db)):
    """Approve pending agent actions and execute them."""
    approval = await db.get(AgentApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status.value}")

    approval.status = ApprovalStatus.APPROVED
    approval.reviewed_at = datetime.now(timezone.utc)

    # Execute the approved actions
    agent = await db.get(AgentConfig, approval.agent_id)
    if agent:
        runner = AgentRunner()
        await runner._process_actions(approval.actions, agent, db)

    await db.flush()
    await broadcast("approval.approved", {
        "approval_id": str(approval.id),
        "agent_id": str(approval.agent_id),
        "action_count": len(approval.actions) if isinstance(approval.actions, list) else 0,
    })
    return {"id": str(approval.id), "status": "approved", "actions_executed": True}


@router.post("/{approval_id}/reject")
async def reject_actions(approval_id: UUID, db: AsyncSession = Depends(get_db)):
    """Reject pending agent actions."""
    approval = await db.get(AgentApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Approval already {approval.status.value}")

    approval.status = ApprovalStatus.REJECTED
    approval.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    await broadcast("approval.rejected", {
        "approval_id": str(approval.id),
        "agent_id": str(approval.agent_id),
    })
    return {"id": str(approval.id), "status": "rejected"}
