from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    # Keys come from backend/.env or the environment. Never commit .env.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPEN_AI_API_KEY")
    google_api_key: str | None = Field(default=None, validation_alias="GOOGLE_API_KEY")

    # Models, tried in this order. A failure on one moves on to the next.
    claude_model: str = "claude-opus-5-5"
    openai_model: str = "gpt-5"
    google_model: str = "gemini-3.1-pro-preview"
    provider_order: str = "claude,openai,google"

    # Where tickets are stored, and where the support docs live. Swap DOCS_PATH for your own docs.
    database_path: str = Field(
        default=str(BACKEND_DIR / "var" / "tickets.db"), validation_alias="DATABASE_PATH"
    )
    docs_path: str = Field(default=str(BACKEND_DIR / "data" / "docs"), validation_alias="DOCS_PATH")

    # Who is calling when no identity headers are sent. A placeholder until real sign-in exists.
    default_user: str = Field(default="Reviewer", validation_alias="DEFAULT_USER")
    default_role: str = Field(default="reviewer", validation_alias="DEFAULT_ROLE")

    # Comma-separated origins allowed to call the API (the Vite dev server by default).
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider_names(self) -> list[str]:
        return [p.strip() for p in self.provider_order.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
