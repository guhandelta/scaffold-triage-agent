"""Requests that wait for an admin: list them, see each one's current state, then approve or reject.

Approving runs the change as the person who asked for it, so their permissions still apply.
"""

from fastapi import APIRouter, HTTPException

from app import review
from app.approvals import ApprovalNotFound, ApprovalStore
from app.auth import CurrentUser, require, user_for
from app.deps import ApprovalsDep, ChainDep, ConfigDep, KbDep, PeopleDep, StoreDep
from app.org_config import OrgConfig
from app.routers.tickets import _load
from app.schemas import (
    ApprovalDecisionIn,
    ApprovalDetail,
    ApprovalRequest,
    ApproveIn,
    OverrideIn,
    Permission,
    TeamIn,
    TicketIn,
    User,
)
from app.scope import can_see
from app.service import run_triage
from app.store import TicketNotFound, TicketStore

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _get(approvals: ApprovalStore, approval_id: str) -> ApprovalRequest:
    try:
        return approvals.get(approval_id)
    except ApprovalNotFound:
        raise HTTPException(status_code=404, detail="request not found") from None


def _picked(request: ApprovalRequest, include: list[int] | None) -> list[dict]:
    tickets = request.payload["tickets"]
    if not include:
        return tickets
    if any(i < 0 or i >= len(tickets) for i in include):
        raise HTTPException(status_code=422, detail="include names a ticket not in this batch")
    return [tickets[i] for i in sorted(set(include))]


async def _carry_out(
    request: ApprovalRequest,
    who: User,
    chain,
    store: TicketStore,
    kb,
    config: OrgConfig,
    include: list[int] | None = None,
) -> str:
    """Do the approved change. Returns a note for the record, such as how many of a batch."""
    if request.action == Permission.create:
        require(who, Permission.create)
        chosen = _picked(request, include)
        for raw in chosen:
            await run_triage(TicketIn.model_validate(raw), chain, store, kb, config)
        total = len(request.payload["tickets"])
        return "" if len(chosen) == total else f"approved {len(chosen)} of {total}"
    if request.ticket_id is None:
        raise HTTPException(status_code=409, detail="request names no ticket")
    record = _load(store, request.ticket_id)
    try:
        if request.action == Permission.delete:
            store.save(review.archive(record, who))
            return ""
        if request.action == Permission.move:
            changed = review.set_team(record, TeamIn(**request.payload).team, who)
        else:
            changed = review.override(record, OverrideIn(**request.payload), who)
    except review.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    store.save(changed)
    return ""


@router.get("", response_model=list[ApprovalRequest])
async def list_requests(approvals: ApprovalsDep, user: CurrentUser) -> list[ApprovalRequest]:
    """Admins see every request; everyone else sees only the ones they made. Newest first."""
    if Permission.approve in user.permissions:
        return approvals.list()
    return approvals.list(requested_by=user.name)


@router.get("/{approval_id}", response_model=ApprovalDetail)
async def get_request(
    approval_id: str,
    approvals: ApprovalsDep,
    store: StoreDep,
    people: PeopleDep,
    user: CurrentUser,
) -> ApprovalDetail:
    """One request, with the ticket it changes as it is now. Admins and the requester only."""
    request = _get(approvals, approval_id)
    if Permission.approve not in user.permissions and request.requested_by != user.name:
        raise HTTPException(status_code=404, detail="request not found")
    current = None
    if request.ticket_id is not None:
        try:
            record = store.get(request.ticket_id)
        except TicketNotFound:
            record = None
        if record is not None and can_see(user, record, people.teams_of(user.name)):
            current = record
    return ApprovalDetail(**request.model_dump(), current=current)


@router.post("/{approval_id}/approve", response_model=ApprovalRequest)
async def approve(
    approval_id: str,
    approvals: ApprovalsDep,
    store: StoreDep,
    chain: ChainDep,
    kb: KbDep,
    config: ConfigDep,
    user: CurrentUser,
    body: ApproveIn | None = None,
) -> ApprovalRequest:
    """Approve the request and do the change. For a batch, `include` picks which tickets.

    If the change fails, the request stays pending.
    """
    require(user, Permission.approve)
    request = _get(approvals, approval_id)
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="request is already decided")
    who = user_for(request.requested_by, request.requested_role, config.access)
    include = body.include if body else None
    note = await _carry_out(request, who, chain, store, kb, config, include)
    return approvals.decide(approval_id, True, user.name, note)


@router.post("/{approval_id}/reject", response_model=ApprovalRequest)
async def reject(
    approval_id: str,
    body: ApprovalDecisionIn,
    approvals: ApprovalsDep,
    user: CurrentUser,
) -> ApprovalRequest:
    """Turn the request down. Nothing changes, and a reason is required."""
    require(user, Permission.approve)
    note = body.note.strip()
    if not note:
        raise HTTPException(status_code=422, detail="a reason is required to reject")
    if _get(approvals, approval_id).status != "pending":
        raise HTTPException(status_code=409, detail="request is already decided")
    return approvals.decide(approval_id, False, user.name, note)
