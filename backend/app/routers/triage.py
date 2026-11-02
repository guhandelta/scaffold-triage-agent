from fastapi import APIRouter

from app.schemas import Decision, TicketIn
from app.triage import decide

router = APIRouter(prefix="/api", tags=["triage"])


@router.post("/triage", response_model=Decision)
async def triage(ticket: TicketIn) -> Decision:
    """Decide whether to reply to a ticket or escalate it to a person."""
    return decide(ticket)
