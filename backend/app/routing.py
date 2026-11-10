"""Decide whether a ticket goes to the agent or straight to a person.

Rules run first and are deterministic: anything they flag never reaches the model.
Whatever gets past them goes to the agent, and the agent can still escalate.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.schemas import TicketIn


class Route(StrEnum):
    agent = "agent"
    human = "human"


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason: str


def route_ticket(ticket: TicketIn, human_only: Sequence[str]) -> RouteDecision:
    """Send the ticket to a person when it contains any of the configured phrases."""
    text = f"{ticket.subject} {ticket.body}".lower()
    for phrase in human_only:
        if phrase in text:
            return RouteDecision(Route.human, f"matched rule '{phrase}'")
    return RouteDecision(Route.agent, "no rule matched")
