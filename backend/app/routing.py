"""Decide whether a ticket goes to the agent or straight to a person.

Rules run first and are deterministic: anything they flag never reaches the model.
Whatever gets past them goes to the agent, and the agent can still escalate.
"""

from collections.abc import Mapping, Sequence
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
    team: str | None = None


def _team_for(text: str, teams: Mapping[str, Sequence[str]]) -> str | None:
    for team, phrases in teams.items():
        if any(phrase in text for phrase in phrases):
            return team
    return None


def route_ticket(
    ticket: TicketIn,
    human_only: Sequence[str],
    teams: Mapping[str, Sequence[str]] | None = None,
) -> RouteDecision:
    """Pick the team, and send the ticket to a person when it contains a configured phrase."""
    text = f"{ticket.subject} {ticket.body}".lower()
    team = _team_for(text, teams or {})
    for phrase in human_only:
        if phrase in text:
            return RouteDecision(Route.human, f"matched rule '{phrase}'", team)
    return RouteDecision(Route.agent, "no rule matched", team)
