"""
Agent Output Validation Schemas
"""

from pydantic import BaseModel, Field, field_validator


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

    # Marketing fields
    body: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    relevance_score: float | None = None
    signal_type: str | None = None
    channel_metadata: dict | None = None
    channel: str | None = None
    signal_id: str | None = None

    @field_validator("type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        allowed = {
            "create_task", "update_task",
            "create_note",
            "save_memory", "save_shared_memory",
            "create_signal", "create_content",
        }
        if v not in allowed:
            raise ValueError(f"Unknown action type '{v}'. Allowed: {', '.join(sorted(allowed))}")
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
