from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator


class Action(StrEnum):
    reply = "reply"
    escalate = "escalate"


class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)
    customer_email: str | None = None


class Decision(BaseModel):
    action: Action
    reasoning: str = Field(description="Why this action was chosen")
    reply_text: str | None = Field(default=None, description="Reply to the customer, when replying")

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


class Health(BaseModel):
    status: str
    agent: str


class TicketRecord(BaseModel):
    """A triaged ticket with its decision and the person who owns it, if anyone."""

    ticket_id: str
    ticket: TicketIn
    result: TriageResult
    owner: str | None = None


class AssignIn(BaseModel):
    owner: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
        Field(description="Name of the person handling it"),
    ]
