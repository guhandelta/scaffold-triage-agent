from fastapi import APIRouter

from app.deps import ChainDep, KbDep, StoreDep
from app.schemas import TicketIn, TriageResult
from app.service import run_triage

router = APIRouter(prefix="/api", tags=["triage"])


@router.post("/triage", response_model=TriageResult)
async def triage(ticket: TicketIn, chain: ChainDep, store: StoreDep, kb: KbDep) -> TriageResult:
    """Route the ticket, read the docs, let the models decide, and save it with its history."""
    record = await run_triage(ticket, chain, store, kb)
    return record.result
