from typing import Annotated

from fastapi import APIRouter, Depends

from app.agent import get_chain
from app.agent.providers import FallbackChain
from app.schemas import Decision, TicketIn

router = APIRouter(prefix="/api", tags=["triage"])

ChainDep = Annotated[FallbackChain, Depends(get_chain)]


@router.post("/triage", response_model=Decision)
async def triage(ticket: TicketIn, chain: ChainDep) -> Decision:
    """Decide whether to reply or escalate, trying each configured model in turn."""
    decision, _, _ = await chain.decide(ticket)
    return decision
