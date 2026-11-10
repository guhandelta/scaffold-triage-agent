"""Ticket store: every triaged ticket with its decision, reviewer changes and history.

Two implementations share one interface:
- `MemoryTicketStore` for tests and throwaway runs.
- `SQLiteTicketStore` for the running app, so tickets survive a restart.

The store only saves and loads whole records. The rules for changing a ticket live in
`app.review`, so a database swap never touches them.
"""

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Protocol

from app.config import get_settings
from app.schemas import TicketRecord, TicketStatus


class TicketNotFound(KeyError):
    pass


class TicketStore(Protocol):
    def save(self, record: TicketRecord) -> TicketRecord: ...

    def get(self, ticket_id: str) -> TicketRecord: ...

    def list_all(self) -> list[TicketRecord]: ...

    def escalations(self) -> list[TicketRecord]: ...


class MemoryTicketStore:
    def __init__(self) -> None:
        self._records: dict[str, TicketRecord] = {}
        self._lock = Lock()

    def save(self, record: TicketRecord) -> TicketRecord:
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
        """Open tickets a person must handle, newest first."""
        return [r for r in self.list_all() if r.status == TicketStatus.escalated]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    status    TEXT NOT NULL,
    owner     TEXT,
    record    TEXT NOT NULL
)
"""


class SQLiteTicketStore:
    """Stores each ticket as JSON, with status and owner as columns for queries."""

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

    def save(self, record: TicketRecord) -> TicketRecord:
        # An upsert keeps the row id, so an updated ticket keeps its place in the list.
        with self._lock:
            self._db.execute(
                "INSERT INTO tickets (ticket_id, status, owner, record) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(ticket_id) DO UPDATE SET "
                "status = excluded.status, owner = excluded.owner, record = excluded.record",
                (record.ticket_id, record.status.value, record.owner, record.model_dump_json()),
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
                "SELECT record FROM tickets WHERE status = ? ORDER BY rowid DESC",
                (TicketStatus.escalated.value,),
            ).fetchall()
        return [TicketRecord.model_validate_json(r[0]) for r in rows]


_store: TicketStore | None = None


def get_store() -> TicketStore:
    """The app's store, opened once on first use at the path in settings."""
    global _store
    if _store is None:
        _store = SQLiteTicketStore(get_settings().database_path)
    return _store
