"""Ticket store: every triaged ticket, its decision, and who owns it.

In memory for now. The `TicketStore` interface is what a database-backed store must match.
"""

from threading import Lock

from app.schemas import Action, TicketIn, TicketRecord, TriageResult


class TicketNotFound(KeyError):
    pass


class TicketStore:
    def __init__(self) -> None:
        self._records: dict[str, TicketRecord] = {}
        self._lock = Lock()

    def save(self, ticket: TicketIn, result: TriageResult) -> TicketRecord:
        record = TicketRecord(ticket_id=result.ticket_id, ticket=ticket, result=result, owner=None)
        with self._lock:
            self._records[record.ticket_id] = record
        return record

    def get(self, ticket_id: str) -> TicketRecord:
        with self._lock:
            if ticket_id not in self._records:
                raise TicketNotFound(ticket_id)
            return self._records[ticket_id]

    def escalations(self) -> list[TicketRecord]:
        """Tickets a person must handle: escalated by a rule or by a model."""
        with self._lock:
            items = [
                r for r in self._records.values() if r.result.decision.action == Action.escalate
            ]
        return sorted(items, key=lambda r: r.ticket_id)

    def assign(self, ticket_id: str, owner: str) -> TicketRecord:
        with self._lock:
            if ticket_id not in self._records:
                raise TicketNotFound(ticket_id)
            updated = self._records[ticket_id].model_copy(update={"owner": owner})
            self._records[ticket_id] = updated
            return updated


_store = TicketStore()


def get_store() -> TicketStore:
    return _store
