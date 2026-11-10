from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import review
from app.auth import CurrentUser
from app.deps import ChainDep, KbDep, StoreDep
from app.ingest import UploadError, parse_upload
from app.schemas import AssignIn, NoteIn, OverrideIn, TicketRecord, UploadResult, User
from app.service import run_triage
from app.store import TicketNotFound, TicketStore

router = APIRouter(prefix="/api", tags=["tickets"])


def _load(store: TicketStore, ticket_id: str) -> TicketRecord:
    try:
        return store.get(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="ticket not found") from None


def _apply(store: TicketStore, ticket_id: str, change) -> TicketRecord:
    record = _load(store, ticket_id)
    try:
        return store.save(change(record))
    except review.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/me", response_model=User)
async def me(user: CurrentUser) -> User:
    """Who the API thinks is calling, with their role and permissions."""
    return user


@router.get("/tickets", response_model=list[TicketRecord])
async def list_tickets(store: StoreDep) -> list[TicketRecord]:
    """Every triaged ticket, newest first."""
    return store.list_all()


@router.get("/escalations", response_model=list[TicketRecord])
async def escalations(store: StoreDep) -> list[TicketRecord]:
    """Open tickets a person must handle, newest first."""
    return store.escalations()


@router.post("/tickets/upload", response_model=UploadResult)
async def upload_tickets(
    file: Annotated[UploadFile, File(description=".csv, .md, .txt or .docx")],
    chain: ChainDep,
    store: StoreDep,
    kb: KbDep,
) -> UploadResult:
    """Read tickets from a file and triage each one."""
    filename = file.filename or "upload"
    try:
        tickets = parse_upload(filename, await file.read())
    except UploadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    records = [await run_triage(t, chain, store, kb) for t in tickets]
    return UploadResult(filename=filename, records=records)


@router.get("/tickets/{ticket_id}", response_model=TicketRecord)
async def get_ticket(ticket_id: str, store: StoreDep) -> TicketRecord:
    return _load(store, ticket_id)


@router.post("/tickets/{ticket_id}/assign", response_model=TicketRecord)
async def assign(
    ticket_id: str, body: AssignIn, store: StoreDep, user: CurrentUser
) -> TicketRecord:
    return _apply(store, ticket_id, lambda r: review.assign(r, body.owner, user))


@router.post("/tickets/{ticket_id}/confirm", response_model=TicketRecord)
async def confirm(ticket_id: str, store: StoreDep, user: CurrentUser) -> TicketRecord:
    """Agree with the decision in force."""
    return _apply(store, ticket_id, lambda r: review.confirm(r, user))


@router.post("/tickets/{ticket_id}/override", response_model=TicketRecord)
async def override(
    ticket_id: str, body: OverrideIn, store: StoreDep, user: CurrentUser
) -> TicketRecord:
    """Replace the agent's decision: send a reply instead, or hand it to a person."""
    return _apply(store, ticket_id, lambda r: review.override(r, body, user))


@router.post("/tickets/{ticket_id}/notes", response_model=TicketRecord)
async def add_note(
    ticket_id: str, body: NoteIn, store: StoreDep, user: CurrentUser
) -> TicketRecord:
    return _apply(store, ticket_id, lambda r: review.add_note(r, body.text, user))


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketRecord)
async def resolve(ticket_id: str, store: StoreDep, user: CurrentUser) -> TicketRecord:
    return _apply(store, ticket_id, lambda r: review.resolve(r, user))
