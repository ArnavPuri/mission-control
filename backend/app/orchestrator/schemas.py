"""
Agent Output Validation Schemas

Pydantic models for validating agent JSON output. Ensures agents
return well-formed actions before writing to the database.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Literal


class AgentAction(BaseModel):
    """A single action from an agent's output."""
    type: str

    # Task fields
    text: str | None = None
    priority: str | None = None
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None
    task_id: str | None = None
    status: str | None = None

    # Idea fields (text reused)

    # Note fields
    title: str | None = None
    content: str | None = None
    url: str | None = None
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
            "create_task", "create_idea", "update_task",
            "save_memory", "save_shared_memory",
            "create_note", "create_journal", "create_goal",
            "create_signal", "create_content",
        }
        if v not in allowed:
            raise ValueError(f"Unknown action type '{v}'. Allowed: {', '.join(sorted(allowed))}")
        return v


class AgentOutput(BaseModel):
    """Validated agent output structure."""
    summary: str = ""
    actions: list[AgentAction] = Field(default_factory=list)

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        if not v.strip():
            return "No summary provided"
        return v


def validate_agent_output(raw: dict) -> tuple[AgentOutput, list[str]]:
    """Validate raw agent output dict and return (parsed_output, warnings).

    Returns the validated output and a list of any validation warnings
    (e.g., actions that were dropped due to invalid type).
    """
    warnings = []

    summary = raw.get("summary", "")
    if not summary and not raw.get("actions"):
        # Entire output might be a plain text response
        summary = str(raw) if raw else "No output"

    # Validate actions individually, keeping valid ones and warning about bad ones
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
