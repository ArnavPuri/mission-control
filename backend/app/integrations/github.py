"""
Dev tasks on GitHub.

Coding work isn't done inside Mission Control: a dev task becomes an issue
in the project's repo that mentions @claude, so the Claude GitHub app
(Claude Code) implements it and opens a pull request. Mission Control keeps
the task, links the issue, reports PRs and the issue closing in the task
thread and on Telegram, and forwards your replies as issue comments.
"""

import logging
import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Project, Task, TaskComment, TaskStatus
from app.notifications.dispatcher import send_telegram
from app.orchestrator.reminders import complete_task

logger = logging.getLogger(__name__)

API = "https://api.github.com"
DEV_TAG = "dev"
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
ISSUE_URL_RE = re.compile(r"^https://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")
SYSTEM = "system"


class GitHubError(Exception):
    pass


def configured() -> bool:
    return bool(settings.github_token)


def normalize_repo(value: str | None) -> str | None:
    """Accept "owner/repo" or a github.com URL; return "owner/repo" or None."""
    if not value:
        return None
    value = value.strip().removesuffix(".git").rstrip("/")
    value = re.sub(r"^(https?://)?(www\.)?github\.com/", "", value)
    return value if REPO_RE.match(value) else None


def issue_ref(task: Task) -> tuple[str, int] | None:
    match = ISSUE_URL_RE.match(task.url or "")
    return (match.group(1), int(match.group(2))) if match else None


async def _request(method: str, path: str, json: dict | None = None):
    if not settings.github_token:
        raise GitHubError("GITHUB_TOKEN is not set")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(
            method, f"{API}{path}", json=json,
            headers={
                "Authorization": f"Bearer {settings.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
    if resp.status_code >= 400:
        detail = resp.json().get("message", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        raise GitHubError(f"GitHub {resp.status_code}: {detail}")
    return resp.json()


def _mention() -> str:
    return "\n\n@claude please implement this and open a pull request." if settings.github_mention_claude else ""


async def open_dev_issue(db: AsyncSession, task: Task, project: Project) -> str:
    """Open a GitHub issue for a task in its project's repo. Returns the issue URL."""
    if not project.github_repo:
        raise GitHubError(f"Project {project.name} has no GitHub repo. Set one with /repo {project.name} owner/repo")
    body = (
        f"{task.description or task.text}\n\n---\n"
        f"Project: {project.name}{' — ' + project.description if project.description else ''}\n"
        f"Opened from Mission Control (task {str(task.id)[:8]})."
        f"{_mention()}"
    )
    issue = await _request("POST", f"/repos/{project.github_repo}/issues", {"title": task.text[:250], "body": body})
    task.url = issue["html_url"]
    task.project_id = project.id
    task.tags = list(dict.fromkeys([*(task.tags or []), DEV_TAG, "github"]))
    if task.status in (TaskStatus.TODO, TaskStatus.BLOCKED):
        task.status = TaskStatus.IN_PROGRESS
    pickup = " Claude Code will pick it up." if settings.github_mention_claude else ""
    db.add(TaskComment(
        task_id=task.id, author=SYSTEM,
        body=f"Opened issue #{issue['number']} in {project.github_repo}: {issue['html_url']}.{pickup}",
    ))
    await db.commit()
    return issue["html_url"]


async def forward_reply(task: Task, body: str) -> bool:
    """Post a thread reply on the task's GitHub issue. Returns True if posted."""
    ref = issue_ref(task)
    if not ref or not configured():
        return False
    repo, number = ref
    mention = "@claude " if settings.github_mention_claude else ""
    await _request("POST", f"/repos/{repo}/issues/{number}/comments", {"body": f"{mention}{body}"})
    return True


async def _linked_pull_requests(repo: str, number: int) -> list[dict]:
    events = await _request("GET", f"/repos/{repo}/issues/{number}/timeline?per_page=100")
    prs = {}
    for event in events:
        source = (event.get("source") or {}).get("issue") or {}
        if event.get("event") == "cross-referenced" and "pull_request" in source:
            prs[source["html_url"]] = {"url": source["html_url"], "title": source.get("title", "")}
    return list(prs.values())


async def sync_dev_tasks(db: AsyncSession):
    """Report new PRs and closed issues for open dev tasks."""
    result = await db.execute(select(Task).where(Task.status != TaskStatus.DONE))
    tasks = [t for t in result.scalars().all() if DEV_TAG in (t.tags or []) and issue_ref(t)]
    for task in tasks:
        repo, number = issue_ref(task)
        try:
            issue = await _request("GET", f"/repos/{repo}/issues/{number}")
            prs = await _linked_pull_requests(repo, number)
        except GitHubError as e:
            logger.warning(f"GitHub sync for {repo}#{number} failed: {e}")
            continue

        thread = (await db.execute(select(TaskComment.body).where(TaskComment.task_id == task.id))).scalars().all()
        for pr in prs:
            if any(pr["url"] in body for body in thread):
                continue
            text = f"Pull request opened: {pr['title']} {pr['url']}"
            comment = TaskComment(task_id=task.id, author=SYSTEM, body=text)
            db.add(comment)
            comment.telegram_message_id = await send_telegram(
                f"🔀 {task.text[:80]}\n{text}\n\nReply to this message to comment on the issue."
            )

        if issue.get("state") == "closed":
            await complete_task(db, task, source="github")
            text = f"Issue #{number} was closed on GitHub."
            db.add(TaskComment(task_id=task.id, author=SYSTEM, body=text))
            await send_telegram(f"✅ {task.text[:80]}\n{text}")
        await db.commit()
