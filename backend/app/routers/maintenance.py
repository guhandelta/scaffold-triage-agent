"""Cleanup, with an admin in the loop.

The sweep never changes anything itself. It raises a notice for each step it would take: closing
a stale request, or removing an old request or archived ticket. An admin confirms each notice to
carry it out, or dismisses it. Tickets marked keep are never proposed for removal.
"""

from datetime import timedelta

from fastapi import APIRouter, HTTPException

from app.approvals import ApprovalNotFound, NoticeNotFound
from app.auth import CurrentUser, require
from app.deps import ApprovalsDep, ConfigDep, StoreDep
from app.schemas import CleanupKind, Notice, NoticeStatus, Permission, SweepResult, now
from app.store import TicketNotFound

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def _gone(store, ticket_id: str) -> bool:
    try:
        return store.get(ticket_id).archived_at is not None
    except TicketNotFound:
        return True


def _raise_if_not_open(notice: Notice) -> None:
    if notice.status != NoticeStatus.open:
        raise HTTPException(status_code=409, detail="notice is already decided")


@router.post("/sweep", response_model=SweepResult)
async def sweep(
    store: StoreDep, approvals: ApprovalsDep, config: ConfigDep, user: CurrentUser
) -> SweepResult:
    """Look for cleanup steps and raise a notice for each. Nothing is changed here."""
    require(user, Permission.approve)
    require(user, Permission.delete)
    retention = config.retention
    current = now()
    noticed = 0

    def propose(kind: CleanupKind, target: str, summary: str) -> None:
        nonlocal noticed
        if not approvals.has_notice(target):
            approvals.add_notice(kind, target, summary)
            noticed += 1

    expiry_cutoff = current - timedelta(days=retention.request_expiry_days)
    for request in approvals.pending():
        if request.ticket_id is not None and _gone(store, request.ticket_id):
            reason = "its ticket was archived or removed"
        elif request.created_at < expiry_cutoff:
            reason = f"nobody decided it in {retention.request_expiry_days} days"
        else:
            continue
        propose(CleanupKind.expire_request, request.id, f"Close as expired: {reason}")

    for request in approvals.decided_before(
        current - timedelta(days=retention.decided_requests_days)
    ):
        propose(CleanupKind.remove_request, request.id, f"Remove a {request.status.value} request")

    ticket_cutoff = current - timedelta(days=retention.archived_days)
    for record in store.list_all():
        if (
            record.archived_at is not None
            and record.archived_at < ticket_cutoff
            and not record.keep
        ):
            propose(
                CleanupKind.remove_ticket,
                record.ticket_id,
                f"Remove archived ticket {record.ticket_id}",
            )
    return SweepResult(noticed=noticed)


@router.get("/notices", response_model=list[Notice])
async def open_notices(approvals: ApprovalsDep, user: CurrentUser) -> list[Notice]:
    """Cleanup steps waiting for an admin."""
    require(user, Permission.approve)
    return approvals.open_notices()


@router.post("/notices/{notice_id}/confirm", response_model=Notice)
async def confirm(
    notice_id: str,
    approvals: ApprovalsDep,
    store: StoreDep,
    user: CurrentUser,
) -> Notice:
    """Carry out one cleanup step the admin has agreed to."""
    require(user, Permission.approve)
    require(user, Permission.delete)
    try:
        notice = approvals.get_notice(notice_id)
    except NoticeNotFound:
        raise HTTPException(status_code=404, detail="notice not found") from None
    _raise_if_not_open(notice)

    if notice.kind == CleanupKind.expire_request:
        try:
            approvals.expire(notice.target_id, notice.summary, user.name)
        except ApprovalNotFound:
            raise HTTPException(status_code=404, detail="request not found") from None
    elif notice.kind == CleanupKind.remove_request:
        approvals.delete_request(notice.target_id)
    else:
        try:
            record = store.get(notice.target_id)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="ticket not found") from None
        if record.archived_at is None or record.keep:
            raise HTTPException(status_code=409, detail="ticket is no longer archived or is kept")
        store.delete(notice.target_id)
    return approvals.close_notice(notice_id, NoticeStatus.done, user.name)


@router.post("/notices/{notice_id}/dismiss", response_model=Notice)
async def dismiss(notice_id: str, approvals: ApprovalsDep, user: CurrentUser) -> Notice:
    """Turn the step down. Nothing is changed, and it is not raised again."""
    require(user, Permission.approve)
    try:
        notice = approvals.get_notice(notice_id)
    except NoticeNotFound:
        raise HTTPException(status_code=404, detail="notice not found") from None
    _raise_if_not_open(notice)
    return approvals.close_notice(notice_id, NoticeStatus.dismissed, user.name)
