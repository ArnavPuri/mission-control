"""
Mission Control Python SDK

Thin httpx wrapper for the Mission Control REST API.

Usage:
    from mission_control import MissionControl

    mc = MissionControl(base_url="http://localhost:8000", api_key="mc_...")
    tasks = mc.tasks.list()
    mc.tasks.create(text="Buy groceries", priority="high")
    mc.ideas.create(text="New feature idea")
    mc.agents.run("daily-standup")
"""

from __future__ import annotations

from typing import Any

import httpx


class _Resource:
    """Base class for API resource namespaces."""

    def __init__(self, client: MissionControl, prefix: str) -> None:
        self._client = client
        self._prefix = prefix

    def _url(self, path: str = "") -> str:
        return f"/api/{self._prefix}{path}"

    def list(self, **params: Any) -> list[dict]:
        """List all resources, with optional query parameters."""
        return self._client._request("GET", self._url(), params=params)

    def get(self, id: str) -> dict:
        """Get a single resource by ID."""
        return self._client._request("GET", self._url(f"/{id}"))

    def create(self, **data: Any) -> dict:
        """Create a new resource."""
        return self._client._request("POST", self._url(), json=data)

    def update(self, id: str, **data: Any) -> dict:
        """Update an existing resource."""
        return self._client._request("PATCH", self._url(f"/{id}"), json=data)

    def delete(self, id: str) -> dict:
        """Delete a resource by ID."""
        return self._client._request("DELETE", self._url(f"/{id}"))


class _AsyncResource:
    """Base class for async API resource namespaces."""

    def __init__(self, client: AsyncMissionControl, prefix: str) -> None:
        self._client = client
        self._prefix = prefix

    def _url(self, path: str = "") -> str:
        return f"/api/{self._prefix}{path}"

    async def list(self, **params: Any) -> list[dict]:
        return await self._client._request("GET", self._url(), params=params)

    async def get(self, id: str) -> dict:
        return await self._client._request("GET", self._url(f"/{id}"))

    async def create(self, **data: Any) -> dict:
        return await self._client._request("POST", self._url(), json=data)

    async def update(self, id: str, **data: Any) -> dict:
        return await self._client._request("PATCH", self._url(f"/{id}"), json=data)

    async def delete(self, id: str) -> dict:
        return await self._client._request("DELETE", self._url(f"/{id}"))


# ---------------------------------------------------------------------------
# Specialised resource classes (sync)
# ---------------------------------------------------------------------------


class Tasks(_Resource):
    """Tasks resource — /api/tasks."""

    def __init__(self, client: MissionControl) -> None:
        super().__init__(client, "tasks")

    def list(self, *, status: str | None = None, project_id: str | None = None) -> list[dict]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if project_id:
            params["project_id"] = project_id
        return self._client._request("GET", self._url(), params=params)

    def reorder(self, task_ids: list[str]) -> dict:
        """Reorder tasks by providing ordered list of IDs."""
        return self._client._request("POST", self._url("/reorder"), json={"task_ids": task_ids})


class Ideas(_Resource):
    """Ideas resource — /api/ideas."""

    def __init__(self, client: MissionControl) -> None:
        super().__init__(client, "ideas")


class Notes(_Resource):
    """Notes resource — /api/notes."""

    def __init__(self, client: MissionControl) -> None:
        super().__init__(client, "notes")

    def list(self, *, tag: str | None = None) -> list[dict]:
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag
        return self._client._request("GET", self._url(), params=params)


class Projects(_Resource):
    """Projects resource — /api/projects."""

    def __init__(self, client: MissionControl) -> None:
        super().__init__(client, "projects")

    def health(self, id: str) -> dict:
        """Get project health score."""
        return self._client._request("GET", self._url(f"/{id}/health"))


class Agents(_Resource):
    """Agents resource — /api/agents."""

    def __init__(self, client: MissionControl) -> None:
        super().__init__(client, "agents")

    def run(self, id_or_slug: str, *, dry_run: bool = False) -> dict:
        """Trigger an agent run by ID or slug."""
        params = {"dry_run": "true"} if dry_run else {}
        return self._client._request("POST", self._url(f"/{id_or_slug}/run"), params=params)

    def stop(self, id: str) -> dict:
        """Stop a running agent."""
        return self._client._request("POST", self._url(f"/{id}/stop"))

    def runs(self, id: str, *, limit: int = 20) -> list[dict]:
        """Get recent runs for an agent."""
        return self._client._request("GET", self._url(f"/{id}/runs"), params={"limit": str(limit)})


class Search:
    """Search resource — /api/search."""

    def __init__(self, client: MissionControl) -> None:
        self._client = client

    def query(self, q: str, *, entity_types: str = "all", limit: int = 20) -> dict:
        """Full-text search across tasks, ideas, notes, etc."""
        return self._client._request(
            "GET",
            "/api/search",
            params={"q": q, "entity_types": entity_types, "limit": str(limit)},
        )


# ---------------------------------------------------------------------------
# Specialised resource classes (async)
# ---------------------------------------------------------------------------


class AsyncTasks(_AsyncResource):
    def __init__(self, client: AsyncMissionControl) -> None:
        super().__init__(client, "tasks")

    async def list(self, *, status: str | None = None, project_id: str | None = None) -> list[dict]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if project_id:
            params["project_id"] = project_id
        return await self._client._request("GET", self._url(), params=params)

    async def reorder(self, task_ids: list[str]) -> dict:
        return await self._client._request("POST", self._url("/reorder"), json={"task_ids": task_ids})


class AsyncIdeas(_AsyncResource):
    def __init__(self, client: AsyncMissionControl) -> None:
        super().__init__(client, "ideas")


class AsyncNotes(_AsyncResource):
    def __init__(self, client: AsyncMissionControl) -> None:
        super().__init__(client, "notes")

    async def list(self, *, tag: str | None = None) -> list[dict]:
        params: dict[str, str] = {}
        if tag:
            params["tag"] = tag
        return await self._client._request("GET", self._url(), params=params)


class AsyncProjects(_AsyncResource):
    def __init__(self, client: AsyncMissionControl) -> None:
        super().__init__(client, "projects")

    async def health(self, id: str) -> dict:
        return await self._client._request("GET", self._url(f"/{id}/health"))


class AsyncAgents(_AsyncResource):
    def __init__(self, client: AsyncMissionControl) -> None:
        super().__init__(client, "agents")

    async def run(self, id_or_slug: str, *, dry_run: bool = False) -> dict:
        params = {"dry_run": "true"} if dry_run else {}
        return await self._client._request("POST", self._url(f"/{id_or_slug}/run"), params=params)

    async def stop(self, id: str) -> dict:
        return await self._client._request("POST", self._url(f"/{id}/stop"))

    async def runs(self, id: str, *, limit: int = 20) -> list[dict]:
        return await self._client._request("GET", self._url(f"/{id}/runs"), params={"limit": str(limit)})


class AsyncSearch:
    def __init__(self, client: AsyncMissionControl) -> None:
        self._client = client

    async def query(self, q: str, *, entity_types: str = "all", limit: int = 20) -> dict:
        return await self._client._request(
            "GET",
            "/api/search",
            params={"q": q, "entity_types": entity_types, "limit": str(limit)},
        )


# ---------------------------------------------------------------------------
# Client classes
# ---------------------------------------------------------------------------


class MissionControl:
    """Synchronous Mission Control API client.

    Args:
        base_url: API server URL (e.g. ``http://localhost:8000``).
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._http = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )

        # Resource namespaces
        self.tasks = Tasks(self)
        self.ideas = Ideas(self)
        self.notes = Notes(self)
        self.projects = Projects(self)
        self.agents = Agents(self)
        self.search = Search(self)

    # -- internal ----------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any | None = None,
    ) -> Any:
        resp = self._http.request(method, path, params=params, json=json)
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> MissionControl:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncMissionControl:
    """Asynchronous Mission Control API client.

    Args:
        base_url: API server URL (e.g. ``http://localhost:8000``).
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds (default 30).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )

        # Resource namespaces
        self.tasks = AsyncTasks(self)
        self.ideas = AsyncIdeas(self)
        self.notes = AsyncNotes(self)
        self.projects = AsyncProjects(self)
        self.agents = AsyncAgents(self)
        self.search = AsyncSearch(self)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any | None = None,
    ) -> Any:
        resp = await self._http.request(method, path, params=params, json=json)
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncMissionControl:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
