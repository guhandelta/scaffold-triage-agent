from enum import StrEnum

from pydantic import BaseModel, Field


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


class Health(BaseModel):
    status: str
    agent: str
