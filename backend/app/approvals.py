"""Changes an agent may ask for but not make on its own.

A role's permissions say what it may do. The `approval` list in triage.yaml says which of those
actions wait for an admin: the request is saved, nothing changes, and an admin approves or rejects
it. Approving runs the action as the person who asked, so their permissions still apply.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

from fastapi.responses import JSONResponse

from app.config import get_settings
from app.schemas import (
    ApprovalRequest,
    ApprovalStatus,
    CleanupKind,
    Notice,
    NoticeStatus,
    Permission,
    Role,
    User,
    now,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id             TEXT PRIMARY KEY,
    action         TEXT NOT NULL,
    ticket_id      TEXT,
    payload        TEXT NOT NULL,
    requested_by   TEXT NOT NULL,
    requested_role TEXT NOT NULL,
    status         TEXT NOT NULL,
    decided_by     TEXT,
    decision_note  TEXT,
    created_at     TEXT NOT NULL,
    decided_at     TEXT
);
CREATE TABLE IF NOT EXISTS cleanup_notices (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    target_id  TEXT NOT NULL,
    summary    TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT
);
"""

_COLUMNS = (
    "id, action, ticket_id, payload, requested_by, requested_role, status, decided_by, "
    "decision_note, created_at, decided_at"
)


class ApprovalNotFound(KeyError):
    pass


class ApprovalClosed(Exception):
    """The request was already approved or rejected."""


class NoticeNotFound(KeyError):
    pass


class ApprovalStore:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._lock = Lock()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _row(self, row: tuple) -> ApprovalRequest:
        (id_, action, ticket_id, payload, by, role, status, decided_by, note, created, decided) = (
            row
        )
        return ApprovalRequest(
            id=id_,
            action=Permission(action),
            ticket_id=ticket_id,
            payload=json.loads(payload),
            requested_by=by,
            requested_role=Role(role),
            status=ApprovalStatus(status),
            decided_by=decided_by,
            decision_note=note,
            created_at=created,
            decided_at=decided,
        )

    def create(
        self,
        action: Permission,
        ticket_id: str | None,
        payload: dict,
        requested_by: str,
        requested_role: Role,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            id=uuid.uuid4().hex[:12],
            action=action,
            ticket_id=ticket_id,
            payload=payload,
            requested_by=requested_by,
            requested_role=requested_role,
        )
        with self._lock:
            self._db.execute(
                f"INSERT INTO approvals ({_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)",
                (
                    request.id,
                    request.action.value,
                    ticket_id,
                    json.dumps(payload),
                    requested_by,
                    requested_role.value,
                    request.status.value,
                    request.created_at.isoformat(),
                ),
            )
            self._db.commit()
        return request

    def get(self, approval_id: str) -> ApprovalRequest:
        with self._lock:
            row = self._db.execute(
                f"SELECT {_COLUMNS} FROM approvals WHERE id = ?", (approval_id,)
            ).fetchone()
        if row is None:
            raise ApprovalNotFound(approval_id)
        return self._row(row)

    def list(self, requested_by: str | None = None) -> list[ApprovalRequest]:
        """Newest first. Pass a name to see only that person's requests."""
        query = f"SELECT {_COLUMNS} FROM approvals"
        args: tuple = ()
        if requested_by is not None:
            query += " WHERE requested_by = ?"
            args = (requested_by,)
        with self._lock:
            rows = self._db.execute(f"{query} ORDER BY created_at DESC, rowid DESC", args)
            return [self._row(r) for r in rows.fetchall()]

    def pending(self) -> list[ApprovalRequest]:
        return [r for r in self.list() if r.status == ApprovalStatus.pending]

    def expire(self, approval_id: str, note: str, actor: str) -> ApprovalRequest:
        """Close a request nobody can act on any more. It is kept, not deleted."""
        with self._lock:
            self._db.execute(
                "UPDATE approvals SET status = ?, decided_by = ?, decision_note = ?, "
                "decided_at = ? WHERE id = ? AND status = ?",
                (
                    ApprovalStatus.expired.value,
                    actor,
                    note,
                    now().isoformat(),
                    approval_id,
                    ApprovalStatus.pending.value,
                ),
            )
            self._db.commit()
        return self.get(approval_id)

    def decided_before(self, cutoff: datetime) -> list[ApprovalRequest]:
        """Requests decided before the cutoff. Pending ones are never included."""
        return [
            r
            for r in self.list()
            if r.status != ApprovalStatus.pending
            and r.decided_at is not None
            and r.decided_at < cutoff
        ]

    def delete_request(self, approval_id: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM approvals WHERE id = ?", (approval_id,))
            self._db.commit()

    def has_notice(self, target_id: str) -> bool:
        """True if the target already has a notice, open or dismissed, so it is not raised twice."""
        with self._lock:
            row = self._db.execute(
                "SELECT 1 FROM cleanup_notices WHERE target_id = ?", (target_id,)
            ).fetchone()
        return row is not None

    def add_notice(self, kind: CleanupKind, target_id: str, summary: str) -> Notice:
        notice = Notice(id=uuid.uuid4().hex[:12], kind=kind, target_id=target_id, summary=summary)
        with self._lock:
            self._db.execute(
                "INSERT INTO cleanup_notices (id, kind, target_id, summary, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    notice.id,
                    kind.value,
                    target_id,
                    summary,
                    notice.status.value,
                    notice.created_at.isoformat(),
                ),
            )
            self._db.commit()
        return notice

    def _notice_row(self, row: tuple) -> Notice:
        id_, kind, target, summary, status, created, decided_by, decided_at = row
        return Notice(
            id=id_,
            kind=CleanupKind(kind),
            target_id=target,
            summary=summary,
            status=NoticeStatus(status),
            created_at=created,
            decided_by=decided_by,
            decided_at=decided_at,
        )

    def open_notices(self) -> list[Notice]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, kind, target_id, summary, status, created_at, decided_by, decided_at "
                "FROM cleanup_notices WHERE status = ? ORDER BY created_at",
                (NoticeStatus.open.value,),
            ).fetchall()
        return [self._notice_row(r) for r in rows]

    def get_notice(self, notice_id: str) -> Notice:
        with self._lock:
            row = self._db.execute(
                "SELECT id, kind, target_id, summary, status, created_at, decided_by, decided_at "
                "FROM cleanup_notices WHERE id = ?",
                (notice_id,),
            ).fetchone()
        if row is None:
            raise NoticeNotFound(notice_id)
        return self._notice_row(row)

    def close_notice(self, notice_id: str, status: NoticeStatus, actor: str) -> Notice:
        if self.get_notice(notice_id).status != NoticeStatus.open:
            raise ApprovalClosed(notice_id)
        with self._lock:
            self._db.execute(
                "UPDATE cleanup_notices SET status = ?, decided_by = ?, decided_at = ? "
                "WHERE id = ?",
                (status.value, actor, now().isoformat(), notice_id),
            )
            self._db.commit()
        return self.get_notice(notice_id)

    def decide(self, approval_id: str, approve: bool, actor: str, note: str) -> ApprovalRequest:
        current = self.get(approval_id)
        if current.status != ApprovalStatus.pending:
            raise ApprovalClosed(approval_id)
        status = ApprovalStatus.approved if approve else ApprovalStatus.rejected
        with self._lock:
            self._db.execute(
                "UPDATE approvals SET status = ?, decided_by = ?, decision_note = ?, "
                "decided_at = ? WHERE id = ?",
                (status.value, actor, note, now().isoformat(), approval_id),
            )
            self._db.commit()
        return self.get(approval_id)


_store: ApprovalStore | None = None


def get_approval_store() -> ApprovalStore:
    """The app's approval store, opened once on first use in the same database as the tickets."""
    global _store
    if _store is None:
        _store = ApprovalStore(get_settings().database_path)
    return _store


def queue(
    store: ApprovalStore,
    action: Permission,
    user: User,
    payload: dict,
    ticket_id: str | None = None,
) -> JSONResponse:
    """Save the request and answer 202: accepted, waiting for an admin."""
    request = store.create(action, ticket_id, payload, user.name, user.role)
    return JSONResponse(status_code=202, content=request.model_dump(mode="json"))
