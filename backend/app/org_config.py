"""Everything an organization changes to make the agent its own, read from one YAML file.

Secrets (API keys) stay in the environment. Everything else lives in `triage.yaml`: the
organization's name, where its support docs are, which tickets always go to a person, what each
role may do, which models to try, and how replies are worded.

The file is found at TRIAGE_CONFIG, or `backend/triage.yaml` by default. A relative docs path is
read from the folder the config file is in, so an organization can keep its config and docs
together in one folder and mount it anywhere.

Check a file without starting the app:  uv run python -m app.org_config path/to/triage.yaml
"""

import sys
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.config import BACKEND_DIR, get_settings
from app.schemas import Permission, Role

DEFAULT_CONFIG = BACKEND_DIR / "triage.yaml"

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Phrase = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1)]
TeamKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9][a-z0-9-]{0,39}$"),
]
ProviderName = Literal["claude", "openai", "google"]


class _Strict(BaseModel):
    # A misspelled key is an error, not something silently ignored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class Organization(_Strict):
    name: Text = "Your company"
    product: Text | None = Field(default=None, description="Product name, used in the prompt")


class Docs(_Strict):
    path: Text = "data/docs"
    top_k: int = Field(default=4, ge=1, le=20, description="Sections the agent reads per ticket")


DEFAULT_HUMAN_ONLY = (
    "refund",
    "chargeback",
    "charged twice",
    "dispute",
    "lawyer",
    "legal",
    "fraud",
    "hacked",
    "breach",
    "data loss",
    "outage",
    "is down",
    "cancel my account",
)


class Routing(_Strict):
    human_only: list[Phrase] = Field(
        default_factory=lambda: list(DEFAULT_HUMAN_ONLY),
        description="Phrases that send a ticket straight to a person. [] turns this off.",
    )
    teams: dict[TeamKey, list[Phrase]] = Field(
        default_factory=dict,
        description="Team name -> phrases that send a ticket to that team. The first match wins.",
    )


class Models(_Strict):
    claude: Text = "claude-opus-5-5"
    openai: Text = "gpt-5"
    google: Text = "gemini-3.1-pro-preview"


class Agent(_Strict):
    providers: list[ProviderName] = Field(default_factory=lambda: ["claude", "openai", "google"])
    models: Models = Models()
    instructions: str = Field(default="", description="Extra guidance added to the prompt")
    min_score: float = Field(
        default=2.5, ge=0, description="Offline rules: weakest doc match still sent as a reply"
    )


class Replies(_Strict):
    greeting: str = "Hi,"
    closing: str = (
        "If this does not solve it, reply here and a person on our team will take a look."
    )


def _default_roles() -> dict[Role, list[Permission]]:
    return {
        Role.viewer: [],
        Role.agent: [
            Permission.assign,
            Permission.note,
            Permission.create,
            Permission.override,
            Permission.move,
            Permission.delete,
        ],
        Role.reviewer: [
            Permission.assign,
            Permission.note,
            Permission.confirm,
            Permission.override,
            Permission.resolve,
            Permission.create,
            Permission.move,
        ],
        Role.admin: list(Permission),
    }


def _default_approval() -> dict[Role, list[Permission]]:
    # Agents may ask for these, but an admin signs off before they happen.
    return {
        Role.agent: [Permission.create, Permission.override, Permission.move, Permission.delete]
    }


class Access(_Strict):
    default_user: Text = "Reviewer"
    default_role: Role = Role.reviewer
    roles: dict[Role, list[Permission]] = Field(default_factory=_default_roles)
    approval: dict[Role, list[Permission]] = Field(
        default_factory=_default_approval,
        description="Actions a role may request but only an admin can let happen.",
    )

    def permissions(self, role: Role) -> list[Permission]:
        """A role left out of the file may do nothing."""
        return sorted(set(self.roles.get(role, [])))

    def needs_approval(self, role: Role, permission: Permission) -> bool:
        return permission in self.approval.get(role, [])


class Retention(_Strict):
    """How long things are kept. Old items are removed by the admin's cleanup, never sooner."""

    archived_days: int = Field(
        default=365, ge=1, description="Archived tickets are proposed for removal after this."
    )
    decided_requests_days: int = Field(
        default=365, ge=1, description="Approved, rejected or expired requests are kept this long."
    )
    request_expiry_days: int = Field(
        default=30, ge=1, description="A request nobody decides closes as expired after this."
    )


class OrgConfig(_Strict):
    organization: Organization = Organization()
    docs: Docs = Docs()
    routing: Routing = Routing()
    agent: Agent = Agent()
    replies: Replies = Replies()
    access: Access = Access()
    retention: Retention = Retention()

    # Set by `load`: the folder relative paths are read from. Not part of the file.
    base_dir: Path = Field(default=BACKEND_DIR, exclude=True)

    @property
    def docs_dir(self) -> Path:
        path = Path(self.docs.path).expanduser()
        return path if path.is_absolute() else (self.base_dir / path).resolve()


class ConfigError(ValueError):
    pass


def load(path: str | Path) -> OrgConfig:
    """Read and check a config file. Raises ConfigError with a readable message."""
    path = Path(path).expanduser().resolve()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror}") from None
    except yaml.YAMLError as e:
        raise ConfigError(f"{path} is not valid YAML: {e}") from None
    if not isinstance(raw, dict):
        raise ConfigError(f"{path} must be a mapping of settings")
    try:
        return OrgConfig.model_validate({**raw, "base_dir": path.parent})
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'file'}: {err['msg']}" for err in e.errors()
        )
        raise ConfigError(f"{path}: {problems}") from None


@lru_cache
def get_org_config() -> OrgConfig:
    return load(get_settings().triage_config or DEFAULT_CONFIG)


def main(argv: list[str]) -> int:
    path = argv[0] if argv else (get_settings().triage_config or DEFAULT_CONFIG)
    try:
        config = load(path)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1
    docs = config.docs_dir
    files = len(list(docs.rglob("*.md"))) if docs.is_dir() else 0
    print(f"OK: {config.organization.name}")
    print(f"  docs:      {docs} ({files} Markdown file(s))")
    print(f"  providers: {' > '.join(config.agent.providers) or 'offline rules only'}")
    print(f"  to people: {len(config.routing.human_only)} routing phrase(s)")
    for role in Role:
        print(
            f"  {role.value + ':':10} {', '.join(config.access.permissions(role)) or 'view only'}"
        )
    if not docs.is_dir():
        print(f"Warning: the docs folder {docs} does not exist", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
