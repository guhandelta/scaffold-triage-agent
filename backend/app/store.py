"""Ticket store: every triaged ticket, its decision, and who owns it.

Two implementations share one interface:
- `MemoryTicketStore` for tests and throwaway runs.
- `SQLiteTicketStore` for the running app, so tickets survive a restart.
"""

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Protocol

from app.config import get_settings
from app.schemas import Action, TicketIn, TicketRecord, TriageResult


class TicketNotFound(KeyError):
    pass


class TicketStore(Protocol):
    def save(self, ticket: TicketIn, result: TriageResult) -> TicketRecord: ...

    def get(self, ticket_id: str) -> TicketRecord: ...

    def list_all(self) -> list[TicketRecord]: ...

    def escalations(self) -> list[TicketRecord]: ...

    def assign(self, ticket_id: str, owner: str) -> TicketRecord: ...


class MemoryTicketStore:
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

    def list_all(self) -> list[TicketRecord]:
        """Every ticket, newest first."""
        with self._lock:
            return list(reversed(self._records.values()))

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


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    action    TEXT NOT NULL,
    owner     TEXT,
    record    TEXT NOT NULL
)
"""


class SQLiteTicketStore:
    """Stores each ticket as JSON, with action and owner as columns for the queue query."""

    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(_SCHEMA)
        self._db.commit()
        self._lock = Lock()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def save(self, ticket: TicketIn, result: TriageResult) -> TicketRecord:
        record = TicketRecord(ticket_id=result.ticket_id, ticket=ticket, result=result, owner=None)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO tickets (ticket_id, action, owner, record) "
                "VALUES (?, ?, ?, ?)",
                (record.ticket_id, result.decision.action.value, None, record.model_dump_json()),
            )
            self._db.commit()
        return record

    def get(self, ticket_id: str) -> TicketRecord:
        with self._lock:
            row = self._db.execute(
                "SELECT record FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
        if row is None:
            raise TicketNotFound(ticket_id)
        return TicketRecord.model_validate_json(row[0])

    def list_all(self) -> list[TicketRecord]:
        with self._lock:
            rows = self._db.execute("SELECT record FROM tickets ORDER BY rowid DESC").fetchall()
        return [TicketRecord.model_validate_json(r[0]) for r in rows]

    def escalations(self) -> list[TicketRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT record FROM tickets WHERE action = ? ORDER BY ticket_id",
                (Action.escalate.value,),
            ).fetchall()
        return [TicketRecord.model_validate_json(r[0]) for r in rows]

    def assign(self, ticket_id: str, owner: str) -> TicketRecord:
        with self._lock:
            row = self._db.execute(
                "SELECT record FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if row is None:
                raise TicketNotFound(ticket_id)
            updated = TicketRecord.model_validate_json(row[0]).model_copy(update={"owner": owner})
            self._db.execute(
                "UPDATE tickets SET owner = ?, record = ? WHERE ticket_id = ?",
                (owner, updated.model_dump_json(), ticket_id),
            )
            self._db.commit()
        return updated


_store: TicketStore | None = None


def get_store() -> TicketStore:
    """The app's store, opened once on first use at the path in settings."""
    global _store
    if _store is None:
        _store = SQLiteTicketStore(get_settings().database_path)
    return _store
