"""
Mission Control - Configuration

Supports multiple LLM auth methods:
  1. ANTHROPIC_API_KEY (recommended)
  2. CLAUDE_CODE_OAUTH_TOKEN (subscription-based, may expire)
  3. OPENROUTER_API_KEY / OLLAMA_BASE_URL (alternative providers)
"""

import re
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
from enum import Enum


class LLMProvider(str, Enum):
    ANTHROPIC_API = "anthropic_api"
    ANTHROPIC_OAUTH = "anthropic_oauth"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    # --- Database ---
    database_url: str = "postgresql+asyncpg://missionctl:missionctl@localhost:5432/missioncontrol"
    use_sqlite: bool = False  # Set True for zero-config local dev (no Postgres needed)
    sqlite_path: str = "data/mission_control.db"
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM Auth (multiple options) ---
    anthropic_api_key: str | None = None
    claude_code_oauth_token: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str | None = None

    # --- Model Defaults ---
    default_model: str = "claude-haiku-4-5"
    smart_model: str = "claude-sonnet-4-6"
    max_agent_budget_usd: float = 0.50

    # --- Chat Assistant ---
    chat_model: str = "claude-sonnet-4-6"
    chat_session_timeout_minutes: int = 30

    # --- Telegram ---
    telegram_bot_token: str | None = None
    telegram_allowed_users: str | None = None  # comma-separated IDs

    # --- Discord ---
    discord_bot_token: str | None = None
    discord_allowed_channels: str | None = None  # comma-separated channel IDs

    # --- GitHub ---
    github_token: str | None = None  # for API access (optional, enhances sync)

    # --- Identity ---
    bot_name: str = "MC"
    identity_file: str = "workspace/identity.md"

    # --- Paths ---
    agent_workdir: str = "/app/workdir"
    skills_dir: str = "skills"

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def effective_database_url(self) -> str:
        """Return the actual database URL, considering SQLite mode."""
        if self.use_sqlite or self.database_url.startswith("sqlite"):
            return f"sqlite+aiosqlite:///{self.sqlite_path}"
        return self.database_url

    @property
    def is_sqlite(self) -> bool:
        return self.use_sqlite or self.database_url.startswith("sqlite")

    @property
    def llm_provider(self) -> LLMProvider:
        """Detect which LLM auth method is configured."""
        if self.anthropic_api_key:
            return LLMProvider.ANTHROPIC_API
        if self.claude_code_oauth_token:
            return LLMProvider.ANTHROPIC_OAUTH
        if self.openrouter_api_key:
            return LLMProvider.OPENROUTER
        if self.ollama_base_url:
            return LLMProvider.OLLAMA
        raise ValueError(
            "No LLM provider configured. Set ANTHROPIC_API_KEY, "
            "CLAUDE_CODE_OAUTH_TOKEN, OPENROUTER_API_KEY, or OLLAMA_BASE_URL"
        )

    @property
    def discord_channel_ids(self) -> list[int]:
        if not self.discord_allowed_channels:
            return []
        return [int(cid.strip()) for cid in self.discord_allowed_channels.split(",") if cid.strip()]

    @property
    def telegram_allowed_user_ids(self) -> list[int]:
        if not self.telegram_allowed_users:
            return []
        return [int(uid.strip()) for uid in self.telegram_allowed_users.split(",") if uid.strip()]


    @property
    def identity(self) -> str:
        """Load user identity from workspace/identity.md."""
        for search_path in [self.identity_file, f"../{self.identity_file}"]:
            path = Path(search_path)
            if path.exists():
                return path.read_text().strip()
        return ""

    @property
    def bot_personality(self) -> dict:
        """Extract bot personality fields from identity file."""
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
