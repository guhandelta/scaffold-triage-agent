from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, computed_field, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


def now() -> datetime:
    return datetime.now(UTC)


class Action(StrEnum):
    reply = "reply"
    escalate = "escalate"


class TicketStatus(StrEnum):
    replied = "replied"  # the agent (or a reviewer) answered it
    escalated = "escalated"  # a person must handle it
    resolved = "resolved"  # a reviewer closed it


class Role(StrEnum):
    viewer = "viewer"
    agent = "agent"
    reviewer = "reviewer"
    admin = "admin"


class Permission(StrEnum):
    assign = "assign"
    note = "note"
    confirm = "confirm"
    override = "override"
    resolve = "resolve"


class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)
    customer_email: str | None = None


class Source(BaseModel):
    """One section of the support docs, as retrieved for a ticket."""

    id: str = Field(description="Stable id: area/doc#section")
    area: str
    title: str
    heading: str
    text: str
    human_only: bool = Field(description="The docs say a person must handle this")
    policy: bool = Field(description="Guidance for the agent, never sent to customers")
    score: float


class Decision(BaseModel):
    action: Action
    reasoning: str = Field(description="Why this action was chosen")
    reply_text: str | None = Field(default=None, description="Reply to the customer, when replying")
    citations: list[str] = Field(default_factory=list, description="Ids of the sources used")

    @model_validator(mode="after")
    def reply_needs_text(self) -> "Decision":
        # A "reply" with no text would send the customer nothing. Reject it so the chain
        # moves on to the next model instead of returning an empty answer.
        if self.action == Action.reply and not (self.reply_text or "").strip():
            raise ValueError("a reply decision needs reply_text")
        return self


class TriageResult(BaseModel):
    """A decision plus how it was reached: which model answered, and what failed first."""

    decision: Decision
    route: str = Field(description="agent or human, from the routing rules")
    provider: str = Field(description="Model that decided, or rules / none")
    failed_attempts: list[str] = Field(description="Models that failed before this one")
    ticket_id: str
    sources: list[Source] = Field(default_factory=list, description="Doc sections the agent read")


class HistoryEvent(BaseModel):
    kind: str = Field(description="received, routed, retrieved, error, decided, grounding, ...")
    detail: str
    actor: str = Field(description="agent, rules, or the reviewer's name")
    at: datetime = Field(default_factory=now)


class Note(BaseModel):
    author: str
    text: str
    at: datetime = Field(default_factory=now)


class TicketRecord(BaseModel):
    """A triaged ticket: the agent's decision, reviewer changes, and everything that happened."""

    ticket_id: str
    ticket: TicketIn
    result: TriageResult
    status: TicketStatus
    owner: str | None = None
    override: Decision | None = Field(default=None, description="A reviewer's replacement decision")
    confirmed_by: str | None = None
    notes: list[Note] = Field(default_factory=list)
    history: list[HistoryEvent] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def decision(self) -> Decision:
        """The decision in force: a reviewer's override, or else the agent's."""
        return self.override or self.result.decision


class Health(BaseModel):
    status: str
    agent: str
    docs: int = Field(description="Doc sections the agent can read")


class User(BaseModel):
    name: str
    role: Role
    permissions: list[Permission]


class AssignIn(BaseModel):
    owner: Annotated[Name, Field(description="Name of the person handling it")]


class NoteIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class OverrideIn(BaseModel):
    action: Action
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    reply_text: str | None = None


class UploadResult(BaseModel):
    filename: str
    records: list[TicketRecord]
