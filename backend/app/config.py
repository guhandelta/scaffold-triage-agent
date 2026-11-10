"""Settings from the environment: secrets, file locations, and optional overrides.

How the agent behaves for an organization lives in `triage.yaml` (see `app.org_config`).
The environment only holds what differs per machine: API keys, where files are, and, for
convenience, overrides of the models and their order.
"""

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

    # The organization's config file. Defaults to backend/triage.yaml.
    triage_config: str | None = Field(default=None, validation_alias="TRIAGE_CONFIG")

    # Optional overrides of triage.yaml, handy for trying a model without editing the file.
    claude_model: str | None = Field(default=None, validation_alias="CLAUDE_MODEL")
    openai_model: str | None = Field(default=None, validation_alias="OPENAI_MODEL")
    google_model: str | None = Field(default=None, validation_alias="GOOGLE_MODEL")
    provider_order: str | None = Field(default=None, validation_alias="PROVIDER_ORDER")
    docs_path: str | None = Field(default=None, validation_alias="DOCS_PATH")

    # Where tickets are stored.
    database_path: str = Field(
        default=str(BACKEND_DIR / "var" / "tickets.db"), validation_alias="DATABASE_PATH"
    )

    # Comma-separated origins allowed to call the API (the Vite dev server by default).
    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def provider_names(self) -> list[str] | None:
        if self.provider_order is None:
            return None
        return [p.strip() for p in self.provider_order.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
