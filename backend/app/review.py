"""What a person can do to a triaged ticket, and who may do it.

Every action checks the caller's permission, checks the ticket's state, and adds a history event
with the caller as the actor. The store only saves the result.
"""

from pydantic import ValidationError

from app.auth import require
from app.schemas import (
    Decision,
    HistoryEvent,
    Note,
    OverrideIn,
    Permission,
    TicketRecord,
    TicketStatus,
    User,
    now,
)
from app.service import status_for


class ReviewError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _with(record: TicketRecord, kind: str, detail: str, user: User, **changes) -> TicketRecord:
    event = HistoryEvent(kind=kind, detail=detail, actor=user.name)
    return record.model_copy(update={**changes, "history": [*record.history, event]})


def _open(record: TicketRecord) -> None:
    if record.archived_at is not None:
        raise ReviewError(409, "ticket is archived")
    if record.status == TicketStatus.resolved:
        raise ReviewError(409, "ticket is already resolved")


def archive(record: TicketRecord, user: User) -> TicketRecord:
    """Hide a ticket from everyone's lists. It is kept until the cleanup removes it."""
    require(user, Permission.delete)
    if record.archived_at is not None:
        raise ReviewError(409, "ticket is already archived")
    return _with(record, "archived", "Archived", user, archived_at=now(), archived_by=user.name)


def set_keep(record: TicketRecord, keep: bool, user: User) -> TicketRecord:
    """Label a ticket so the cleanup never removes it, or take the label off."""
    require(user, Permission.delete)
    text = "Marked to keep" if keep else "Removed the keep mark"
    return _with(record, "kept" if keep else "unkept", text, user, keep=keep)


def restore(record: TicketRecord, user: User) -> TicketRecord:
    require(user, Permission.delete)
    if record.archived_at is None:
        raise ReviewError(409, "ticket is not archived")
    return _with(
        record, "restored", "Restored from the archive", user, archived_at=None, archived_by=None
    )


def assign(record: TicketRecord, owner: str, user: User) -> TicketRecord:
    require(user, Permission.assign)
    return _with(record, "assigned", f"Assigned to {owner}", user, owner=owner)


def set_team(record: TicketRecord, team: str, user: User) -> TicketRecord:
    require(user, Permission.assign)
    _open(record)
    return _with(record, "team", f"Moved to team {team}", user, team=team)


def confirm(record: TicketRecord, user: User) -> TicketRecord:
    require(user, Permission.confirm)
    _open(record)
    action = record.decision.action.value
    return _with(
        record, "confirmed", f"Confirmed the decision to {action}", user, confirmed_by=user.name
    )


def override(record: TicketRecord, body: OverrideIn, user: User) -> TicketRecord:
    require(user, Permission.override)
    _open(record)
    try:
        decision = Decision(
            action=body.action,
            reasoning=f"Overridden by {user.name}: {body.reason}",
            reply_text=(body.reply_text or "").strip() or None,
        )
    except ValidationError:
        raise ReviewError(422, "a reply override needs reply_text") from None
    detail = f"Changed the decision to {body.action.value}: {body.reason}"
    return _with(
        record,
        "overridden",
        detail,
        user,
        override=decision,
        status=status_for(decision),
        confirmed_by=None,
    )


def add_note(record: TicketRecord, text: str, user: User) -> TicketRecord:
    require(user, Permission.note)
    note = Note(author=user.name, text=text)
    return _with(record, "note", text, user, notes=[*record.notes, note])


def resolve(record: TicketRecord, user: User) -> TicketRecord:
    require(user, Permission.resolve)
    _open(record)
    return _with(record, "resolved", "Marked as resolved", user, status=TicketStatus.resolved)
