"""
Agent Output Validation Schemas
"""

from pydantic import BaseModel, Field, field_validator, model_validator


ALLOWED_ACTIONS = {
    "create_task", "update_task",
    "create_note",
    "save_memory",
    "create_lead", "create_content",
    "handoff",
}

# Old action names still produced by agents created before leads became tasks
LEGACY_ACTION_ALIASES = {"create_signal": "create_lead"}


class AgentAction(BaseModel):
    type: str

    # Task fields
    text: str | None = None
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    task_id: str | None = None
    status: str | None = None

    # Note fields
    title: str | None = None
    content: str | None = None
    description: str | None = None

    # Memory fields
    key: str | None = None
    value: str | None = None
    memory_type: str | None = None

    # Handoff fields: the teammate's slug and what to ask it
    agent: str | None = None
    request: str | None = None

    # Lead / content fields
    body: str | None = None
    url: str | None = None
    source_type: str | None = None
    relevance_score: float | None = None
    channel: str | None = None

    @model_validator(mode="before")
    @classmethod
    def upgrade_legacy_fields(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["type"] = LEGACY_ACTION_ALIASES.get(data.get("type"), data.get("type"))
        if "source_url" in data and not data.get("url"):
            data["url"] = data.pop("source_url")
        if "signal_id" in data and not data.get("task_id"):
            data["task_id"] = data.pop("signal_id")
        # Task context lists tasks by "id", so agents often reuse that key
        if data.get("type") == "update_task" and "id" in data and not data.get("task_id"):
            data["task_id"] = data.pop("id")
        return data

    @field_validator("type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        if v not in ALLOWED_ACTIONS:
            raise ValueError(f"Unknown action type '{v}'. Allowed: {', '.join(sorted(ALLOWED_ACTIONS))}")
        return v


class AgentOutput(BaseModel):
    summary: str = ""
    actions: list[AgentAction] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        if not v.strip():
            return "No summary provided"
        return v


def validate_agent_output(raw: dict) -> tuple[AgentOutput, list[str]]:
    warnings = []

    summary = raw.get("summary", "")
    if not summary and not raw.get("actions"):
        summary = str(raw) if raw else "No output"

    valid_actions = []
    for i, action in enumerate(raw.get("actions", [])):
        if not isinstance(action, dict):
            warnings.append(f"Action {i}: not a dict, skipped")
            continue
        try:
            valid_actions.append(AgentAction(**action))
        except Exception as e:
            warnings.append(f"Action {i} ({action.get('type', '?')}): {e}")

    output = AgentOutput(summary=summary, actions=valid_actions)
    return output, warnings
