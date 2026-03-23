"""
Mission Control - Configuration

Telegram-first AI assistant. Uses Claude Code subscription (OAuth) exclusively.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Database ---
    database_url: str = "postgresql+asyncpg://missionctl:missionctl@localhost:5432/missioncontrol"
    use_sqlite: bool = False
    sqlite_path: str = "data/mission_control.db"
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM Auth (Claude Code subscription) ---
    claude_code_oauth_token: str | None = None

    # --- Model Defaults ---
    default_model: str = "claude-haiku-4-5"
    smart_model: str = "claude-sonnet-4-6"
    max_agent_budget_usd: float = 0.50

    # --- Chat Assistant ---
    chat_model: str = "claude-sonnet-4-6"
    chat_session_timeout_minutes: int = 30

    # --- Telegram ---
    telegram_bot_token: str | None = None
    telegram_allowed_users: str | None = None
    telegram_notification_chat_id: str | None = None
    notification_timezone: str = "UTC"

    # --- Identity ---
    bot_name: str = "MC"
    identity_file: str = "workspace/identity.md"

    # --- Voice (optional) ---
    openai_api_key: str | None = None

    # --- Paths ---
    agent_workdir: str = "/app/workdir"
    skills_dir: str = "skills"

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def effective_database_url(self) -> str:
        if self.use_sqlite or self.database_url.startswith("sqlite"):
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return self.database_url

    @property
    def is_sqlite(self) -> bool:
        return self.use_sqlite or self.database_url.startswith("sqlite")

    @property
    def llm_configured(self) -> bool:
        return bool(self.claude_code_oauth_token)

    @property
    def telegram_allowed_user_ids(self) -> list[int]:
        if not self.telegram_allowed_users:
            return []
        return [int(uid.strip()) for uid in self.telegram_allowed_users.split(",") if uid.strip()]

    @property
    def telegram_target_chat_id(self) -> str | None:
        if self.telegram_notification_chat_id:
            return self.telegram_notification_chat_id
        allowed = (self.telegram_allowed_users or "").split(",")
        return allowed[0].strip() if allowed and allowed[0].strip() else None

    @property
    def identity(self) -> str:
        for search_path in [self.identity_file, f"../{self.identity_file}"]:
            path = Path(search_path)
            if path.exists():
                return path.read_text().strip()
        return ""

    @property
    def bot_personality(self) -> dict:
        text = self.identity
        if not text:
            return {"name": self.bot_name, "tone": "", "style": ""}

        result = {"name": self.bot_name, "tone": "", "style": ""}
        for line in text.split("\n"):
            line = line.strip()
            if line.lower().startswith("name:"):
                result["name"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("tone:"):
                result["tone"] = line.split(":", 1)[1].strip()
            elif line.lower().startswith("style:"):
                result["style"] = line.split(":", 1)[1].strip()
        return result


settings = Settings()
