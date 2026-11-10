from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import AssignIn, TicketRecord
from app.store import TicketNotFound, TicketStore, get_store

router = APIRouter(prefix="/api", tags=["tickets"])

StoreDep = Annotated[TicketStore, Depends(get_store)]


@router.get("/tickets", response_model=list[TicketRecord])
async def list_tickets(store: StoreDep) -> list[TicketRecord]:
    """Every triaged ticket, newest first."""
    return store.list_all()


@router.get("/escalations", response_model=list[TicketRecord])
async def escalations(store: StoreDep) -> list[TicketRecord]:
    """Every ticket a person must handle, with its owner if one is assigned."""
    return store.escalations()


@router.get("/tickets/{ticket_id}", response_model=TicketRecord)
async def get_ticket(ticket_id: str, store: StoreDep) -> TicketRecord:
    try:
        return store.get(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="ticket not found") from None


@router.post("/tickets/{ticket_id}/assign", response_model=TicketRecord)
async def assign(ticket_id: str, body: AssignIn, store: StoreDep) -> TicketRecord:
    try:
        return store.assign(ticket_id, body.owner)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="ticket not found") from None
