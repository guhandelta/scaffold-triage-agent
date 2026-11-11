"""Requests that wait for an admin: list them, then approve (the change happens) or reject."""

from fastapi import APIRouter, HTTPException

from app import review
from app.approvals import ApprovalNotFound, ApprovalStore
from app.auth import CurrentUser, require, user_for
from app.deps import ApprovalsDep, ChainDep, ConfigDep, KbDep, StoreDep
from app.org_config import OrgConfig
from app.routers.tickets import _load
from app.schemas import (
    ApprovalDecisionIn,
    ApprovalRequest,
    OverrideIn,
    Permission,
    TeamIn,
    TicketIn,
    User,
)
from app.service import run_triage
from app.store import TicketNotFound, TicketStore

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def _get(approvals: ApprovalStore, approval_id: str) -> ApprovalRequest:
    try:
        return approvals.get(approval_id)
    except ApprovalNotFound:
        raise HTTPException(status_code=404, detail="request not found") from None


async def _carry_out(
    request: ApprovalRequest,
    who: User,
    chain,
    store: TicketStore,
    kb,
    config: OrgConfig,
) -> None:
    """Do the approved change as the person who asked for it, so their permissions still apply."""
    if request.action == Permission.create:
        require(who, Permission.create)
        for raw in request.payload["tickets"]:
            await run_triage(TicketIn.model_validate(raw), chain, store, kb, config)
        return
    if request.ticket_id is None:
        raise HTTPException(status_code=409, detail="request names no ticket")
    if request.action == Permission.delete:
        require(who, Permission.delete)
        try:
            store.delete(request.ticket_id)
        except TicketNotFound:
            raise HTTPException(status_code=404, detail="ticket not found") from None
        return

    record = _load(store, request.ticket_id)
    try:
        if request.action == Permission.move:
            changed = review.set_team(record, TeamIn(**request.payload).team, who)
        else:
            changed = review.override(record, OverrideIn(**request.payload), who)
    except review.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None
    store.save(changed)


@router.get("", response_model=list[ApprovalRequest])
async def list_requests(approvals: ApprovalsDep, user: CurrentUser) -> list[ApprovalRequest]:
    """Admins see every request; everyone else sees only the ones they made. Newest first."""
    if Permission.approve in user.permissions:
        return approvals.list()
    return approvals.list(requested_by=user.name)


@router.post("/{approval_id}/approve", response_model=ApprovalRequest)
async def approve(
    approval_id: str,
    approvals: ApprovalsDep,
    store: StoreDep,
    chain: ChainDep,
    kb: KbDep,
    config: ConfigDep,
    user: CurrentUser,
) -> ApprovalRequest:
    """Approve the request and do the change. If the change fails, the request stays pending."""
    require(user, Permission.approve)
    request = _get(approvals, approval_id)
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="request is already decided")
    who = user_for(request.requested_by, request.requested_role, config.access)
    await _carry_out(request, who, chain, store, kb, config)
    return approvals.decide(approval_id, True, user.name, "")


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
