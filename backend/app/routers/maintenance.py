"""Admin cleanup: close stale requests, then remove what has been kept long enough.

Nothing is removed sooner than the retention periods in triage.yaml. An admin runs this, which
is the approval for the removal.
"""

from datetime import timedelta

from fastapi import APIRouter

from app.auth import CurrentUser, require
from app.deps import ApprovalsDep, ConfigDep, StoreDep
from app.schemas import Permission, SweepResult, now
from app.store import TicketNotFound

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


def _gone(store, ticket_id: str) -> bool:
    try:
        return store.get(ticket_id).archived_at is not None
    except TicketNotFound:
        return True


@router.post("/sweep", response_model=SweepResult)
async def sweep(
    store: StoreDep, approvals: ApprovalsDep, config: ConfigDep, user: CurrentUser
) -> SweepResult:
    """Expire requests nobody can act on, then purge archived tickets and old decided requests."""
    require(user, Permission.approve)
    require(user, Permission.delete)
    retention = config.retention
    current = now()

    expired = 0
    expiry_cutoff = current - timedelta(days=retention.request_expiry_days)
    for request in approvals.pending():
        if request.ticket_id is not None and _gone(store, request.ticket_id):
            approvals.expire(request.id, "the ticket was archived or removed")
        elif request.created_at < expiry_cutoff:
            approvals.expire(request.id, f"no decision in {retention.request_expiry_days} days")
        else:
            continue
        expired += 1

    purged_requests = approvals.purge_decided_before(
        current - timedelta(days=retention.decided_requests_days)
    )
    ticket_cutoff = current - timedelta(days=retention.archived_days)
    purged_tickets = 0
    for record in store.list_all():
        if record.archived_at is not None and record.archived_at < ticket_cutoff:
            store.delete(record.ticket_id)
            purged_tickets += 1
    return SweepResult(
        expired_requests=expired,
        purged_requests=purged_requests,
        purged_tickets=purged_tickets,
    )
