from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

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
    manage_people = "manage_people"  # add or move people, change roles, deactivate
    create = "create"  # make new tickets, by typing them in or uploading a file
    move = "move"  # move a ticket to another team
    delete = "delete"  # remove a ticket for good
    approve = "approve"  # decide requests that need an admin's sign-off


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
    team: str | None = Field(default=None, description="Team that may see it; None is everyone")
    override: Decision | None = Field(default=None, description="A reviewer's replacement decision")
    confirmed_by: str | None = None
    notes: list[Note] = Field(default_factory=list)
    history: list[HistoryEvent] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def decision(self) -> Decision:
        """The decision in force: a reviewer's override, or else the agent's."""
        return self.override or self.result.decision


def _clean(value: object) -> object:
    """Trim and lower-case before the pattern check, so ' Billing ' is accepted as 'billing'."""
    return value.strip().lower() if isinstance(value, str) else value


TeamName = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$"),
]
Email = Annotated[
    str,
    BeforeValidator(_clean),
    StringConstraints(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class Membership(BaseModel):
    team: str
    role: Role


class Person(BaseModel):
    id: str
    name: str
    email: str | None = None
    active: bool
    memberships: list[Membership] = Field(default_factory=list)


class PersonEvent(BaseModel):
    """One change to a person: joined a team, role changed, deactivated, and so on."""

    kind: str
    detail: str
    actor: str
    at: datetime = Field(default_factory=now)


class PersonIn(BaseModel):
    name: Name
    email: Email | None = None


class MembershipIn(BaseModel):
    team: TeamName
    role: Role


class RoleChangeIn(BaseModel):
    role: Role
    reason: Reason


class StatusIn(BaseModel):
    active: bool
    reason: Reason


class Health(BaseModel):
    status: str
    organization: str = Field(description="Name from triage.yaml")
    agent: str
    docs: int = Field(description="Doc sections the agent can read")


class User(BaseModel):
    name: str
    role: Role
    permissions: list[Permission]


class AssignIn(BaseModel):
    owner: Annotated[Name, Field(description="Name of the person handling it")]


class TeamIn(BaseModel):
    team: TeamName


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ApprovalRequest(BaseModel):
    """A change someone may not make yet. An admin approves it, and only then does it happen."""

    id: str
    action: Permission
    ticket_id: str | None = Field(default=None, description="The ticket it changes, if any")
    payload: dict = Field(default_factory=dict, description="What to do once approved")
    requested_by: str
    requested_role: Role
    status: ApprovalStatus = ApprovalStatus.pending
    decided_by: str | None = None
    decision_note: str | None = None
    created_at: datetime = Field(default_factory=now)
    decided_at: datetime | None = None


class ApprovalDecisionIn(BaseModel):
    note: str = Field(default="", max_length=1000, description="Required when rejecting")


class ApproveIn(BaseModel):
    include: list[int] | None = Field(
        default=None,
        description="For a batch of new tickets: the positions to create. Empty or omitted "
        "means all of them.",
    )


class ApprovalDetail(ApprovalRequest):
    """A request plus the ticket it changes as it is now, so the approver sees the current state."""

    current: "TicketRecord | None" = Field(
        default=None, description="The ticket as it is now, if it still exists and you may see it"
    )


class NoteIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class OverrideIn(BaseModel):
    action: Action
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    reply_text: str | None = None


class UploadResult(BaseModel):
    filename: str
    records: list[TicketRecord]
