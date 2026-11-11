from fastapi import APIRouter

from app.approvals import queue
from app.auth import CurrentUser, require
from app.deps import ApprovalsDep, ChainDep, ConfigDep, KbDep, StoreDep
from app.schemas import Permission, TicketIn, TriageResult
from app.service import run_triage

router = APIRouter(prefix="/api", tags=["triage"])


@router.post("/triage", response_model=TriageResult, responses={202: {"description": "Waiting"}})
async def triage(
    ticket: TicketIn,
    chain: ChainDep,
    store: StoreDep,
    kb: KbDep,
    config: ConfigDep,
    approvals: ApprovalsDep,
    user: CurrentUser,
):
    """Route the ticket, read the docs, let the models decide, and save it with its history.

    If the caller's role needs an admin's sign-off to create tickets, this answers 202 with the
    request instead, and nothing is triaged until an admin approves it.
    """
    require(user, Permission.create)
    if config.access.needs_approval(user.role, Permission.create):
        return queue(approvals, Permission.create, user, {"tickets": [ticket.model_dump()]})
    record = await run_triage(ticket, chain, store, kb, config)
    return record.result
