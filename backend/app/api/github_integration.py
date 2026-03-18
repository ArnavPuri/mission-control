import hashlib
import hmac
import logging
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import GitHubRepo, Task, EventLog, TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class RepoCreate(BaseModel):
    owner: str
    repo: str
    sync_issues: bool = True
    sync_prs: bool = True
    auto_create_tasks: bool = False
    project_id: str | None = None


class RepoUpdate(BaseModel):
    sync_issues: bool | None = None
    sync_prs: bool | None = None
    auto_create_tasks: bool | None = None
    is_active: bool | None = None
    project_id: str | None = None


@router.get("")
async def list_repos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GitHubRepo).order_by(GitHubRepo.created_at.desc()))
    repos = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "owner": r.owner,
            "repo": r.repo,
            "full_name": f"{r.owner}/{r.repo}",
            "is_active": r.is_active,
            "sync_issues": r.sync_issues,
            "sync_prs": r.sync_prs,
            "auto_create_tasks": r.auto_create_tasks,
            "project_id": str(r.project_id) if r.project_id else None,
            "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in repos
    ]


@router.post("")
async def add_repo(data: RepoCreate, db: AsyncSession = Depends(get_db)):
    import secrets
    webhook_secret = secrets.token_hex(20)

    repo = GitHubRepo(
        **data.model_dump(),
        webhook_secret=webhook_secret,
    )
    db.add(repo)
    await db.flush()
    return {
        "id": str(repo.id),
        "full_name": f"{repo.owner}/{repo.repo}",
        "webhook_secret": webhook_secret,
        "webhook_url": f"/api/github/webhook/{repo.id}",
    }


@router.patch("/{repo_id}")
async def update_repo(repo_id: UUID, data: RepoUpdate, db: AsyncSession = Depends(get_db)):
    repo = await db.get(GitHubRepo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(repo, key, val)
    await db.flush()
    return {"id": str(repo.id), "updated": True}


@router.delete("/{repo_id}")
async def remove_repo(repo_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = await db.get(GitHubRepo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    await db.delete(repo)
    return {"deleted": True}


@router.post("/webhook/{repo_id}")
async def github_webhook(repo_id: UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Receive GitHub webhook events."""
    repo = await db.get(GitHubRepo, repo_id)
    if not repo or not repo.is_active:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if repo.webhook_secret:
        expected = "sha256=" + hmac.new(
            repo.webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    # Process based on event type
    if event_type == "issues" and repo.sync_issues:
        await _handle_issue_event(repo, payload, db)
    elif event_type == "pull_request" and repo.sync_prs:
        await _handle_pr_event(repo, payload, db)

    return {"received": True}


@router.get("/{repo_id}/issues")
async def list_github_tasks(repo_id: UUID, db: AsyncSession = Depends(get_db)):
    """List tasks synced from this GitHub repo."""
    repo = await db.get(GitHubRepo, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    result = await db.execute(
        select(Task).where(
            Task.source == "github",
            Task.tags.any(f"repo:{repo.owner}/{repo.repo}"),
        ).order_by(Task.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "text": t.text,
            "status": t.status.value,
            "tags": t.tags or [],
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


async def _handle_issue_event(repo: GitHubRepo, payload: dict, db: AsyncSession):
    """Process a GitHub issue event."""
    action = payload.get("action")
    issue = payload.get("issue", {})
    issue_number = issue.get("number")
    title = issue.get("title", "")
    state = issue.get("state", "")
    labels = [l.get("name", "") for l in issue.get("labels", [])]

    tag = f"repo:{repo.owner}/{repo.repo}"
    gh_tag = f"gh-issue:{issue_number}"

    # Check if task already exists for this issue
    existing = await db.execute(
        select(Task).where(Task.tags.any(gh_tag), Task.tags.any(tag))
    )
    task = existing.scalar_one_or_none()

    if action == "opened" and repo.auto_create_tasks:
        if not task:
            task = Task(
                text=f"[{repo.owner}/{repo.repo}#{issue_number}] {title}",
                source="github",
                tags=[tag, gh_tag] + [f"label:{l}" for l in labels],
                project_id=repo.project_id,
            )
            db.add(task)
            db.add(EventLog(
                event_type="task.created",
                entity_type="task",
                source="github",
                data={"issue_number": issue_number, "repo": f"{repo.owner}/{repo.repo}"},
            ))
    elif action == "closed" and task:
        task.status = TaskStatus.DONE
    elif action == "reopened" and task:
        task.status = TaskStatus.TODO

    await db.flush()


async def _handle_pr_event(repo: GitHubRepo, payload: dict, db: AsyncSession):
    """Process a GitHub pull request event."""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    pr_number = pr.get("number")
    title = pr.get("title", "")

    tag = f"repo:{repo.owner}/{repo.repo}"
    gh_tag = f"gh-pr:{pr_number}"

    existing = await db.execute(
        select(Task).where(Task.tags.any(gh_tag), Task.tags.any(tag))
    )
    task = existing.scalar_one_or_none()

    if action == "opened" and repo.auto_create_tasks:
        if not task:
            task = Task(
                text=f"[PR {repo.owner}/{repo.repo}#{pr_number}] {title}",
                source="github",
                tags=[tag, gh_tag, "type:pr"],
                project_id=repo.project_id,
            )
            db.add(task)
    elif action in ("closed",) and task:
        merged = pr.get("merged", False)
        task.status = TaskStatus.DONE
        if merged:
            task.tags = list(set((task.tags or []) + ["merged"]))

    await db.flush()
