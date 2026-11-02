"""Per-ticket memory: the events one ticket accumulates while it is being handled.

This is the first memory tier. Customer history and long-term knowledge come later; they
need their own storage and access rules.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Event:
    kind: str  # "route", "tool_call", "tool_result", "decision", "approval", "error"
    payload: dict[str, Any]
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TicketMemory:
    ticket_id: str
    events: list[Event] = field(default_factory=list)

    def record(self, kind: str, **payload: Any) -> None:
        self.events.append(Event(kind=kind, payload=payload))


_memories: dict[str, TicketMemory] = {}


def memory_for(ticket_id: str) -> TicketMemory:
    """Return the memory for a ticket, creating it on first use."""
    if ticket_id not in _memories:
        _memories[ticket_id] = TicketMemory(ticket_id)
    return _memories[ticket_id]
