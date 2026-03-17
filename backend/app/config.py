"""
Mission Control - Configuration

Supports multiple LLM auth methods:
  1. ANTHROPIC_API_KEY (recommended)
  2. CLAUDE_CODE_OAUTH_TOKEN (subscription-based, may expire)
  3. OPENROUTER_API_KEY / OLLAMA_BASE_URL (alternative providers)
"""

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

    # --- Telegram ---
    telegram_bot_token: str | None = None
    telegram_allowed_users: str | None = None  # comma-separated IDs

    # --- Paths ---
    agent_workdir: str = "/app/workdir"
    skills_dir: str = "skills"

    class Config:
        env_file = "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

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
    def telegram_allowed_user_ids(self) -> list[int]:
        if not self.telegram_allowed_users:
            return []
        return [int(uid.strip()) for uid in self.telegram_allowed_users.split(",") if uid.strip()]


settings = Settings()
