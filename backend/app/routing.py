"""Decide whether a ticket goes to the agent or straight to a person.

Rules run first and are deterministic: anything they flag never reaches the model.
Whatever gets past them goes to the agent, and the agent can still escalate.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.schemas import TicketIn


class Route(StrEnum):
    agent = "agent"
    human = "human"


# Always handled by a person, whatever the docs say.
HUMAN_ONLY = (
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


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason: str


def route_ticket(ticket: TicketIn) -> RouteDecision:
    text = f"{ticket.subject} {ticket.body}".lower()
    for phrase in HUMAN_ONLY:
        if phrase in text:
            return RouteDecision(Route.human, f"matched rule '{phrase}'")
    return RouteDecision(Route.agent, "no rule matched")
