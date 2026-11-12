from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import review
from app.approvals import queue
from app.auth import CurrentUser, require
from app.deps import ApprovalsDep, ChainDep, ConfigDep, KbDep, PeopleDep, StoreDep
from app.ingest import UploadError, parse_upload
from app.people import PeopleStore
from app.schemas import (
    AssignIn,
    NoteIn,
    OverrideIn,
    Permission,
    TeamIn,
    TicketRecord,
    UploadResult,
    User,
)
from app.scope import can_see
from app.service import run_triage
from app.store import TicketNotFound, TicketStore

router = APIRouter(prefix="/api", tags=["tickets"])


def _load(store: TicketStore, ticket_id: str) -> TicketRecord:
    try:
        return store.get(ticket_id)
    except TicketNotFound:
        raise HTTPException(status_code=404, detail="ticket not found") from None


def _visible(record: TicketRecord, people: PeopleStore, user: User) -> TicketRecord:
    # Someone outside the team gets the same 404 as a missing ticket, so it isn't revealed.
    if not can_see(user, record, people.teams_of(user.name)):
        raise HTTPException(status_code=404, detail="ticket not found")
    return record


def _apply(
    store: TicketStore, ticket_id: str, change, people: PeopleStore, user: User
) -> TicketRecord:
    record = _visible(_load(store, ticket_id), people, user)
    try:
        return store.save(change(record))
    except review.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from None


@router.get("/me", response_model=User)
async def me(user: CurrentUser) -> User:
    """Who the API thinks is calling, with their role and permissions."""
    return user


def _seen_by(
    records: list[TicketRecord],
    people: PeopleStore,
    user: User,
    include_archived: bool = False,
) -> list[TicketRecord]:
    """What the caller may see. Archived tickets are hidden unless an admin asks for them."""
    teams = people.teams_of(user.name)
    visible = [r for r in records if can_see(user, r, teams)]
    if include_archived and Permission.delete in user.permissions:
        return visible
    return [r for r in visible if r.archived_at is None]


@router.get("/tickets", response_model=list[TicketRecord])
async def list_tickets(
    store: StoreDep,
    people: PeopleDep,
    user: CurrentUser,
    include_archived: bool = False,
) -> list[TicketRecord]:
    """Every triaged ticket the caller may see, newest first."""
    return _seen_by(store.list_all(), people, user, include_archived)


@router.get("/escalations", response_model=list[TicketRecord])
async def escalations(
    store: StoreDep,
    people: PeopleDep,
    user: CurrentUser,
    include_archived: bool = False,
) -> list[TicketRecord]:
    """Open tickets a person must handle that the caller may see, newest first."""
    return _seen_by(store.escalations(), people, user, include_archived)


@router.post("/tickets/upload", response_model=UploadResult)
async def upload_tickets(
    file: Annotated[UploadFile, File(description=".csv, .md, .txt or .docx")],
    chain: ChainDep,
    store: StoreDep,
    kb: KbDep,
    config: ConfigDep,
    approvals: ApprovalsDep,
    user: CurrentUser,
):
    """Read tickets from a file and triage each one. Waits for an admin if the role needs it."""
    require(user, Permission.create)
    filename = file.filename or "upload"
    try:
        tickets = parse_upload(filename, await file.read())
    except UploadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    if config.access.needs_approval(user.role, Permission.create):
        payload = {"filename": filename, "tickets": [t.model_dump() for t in tickets]}
        return queue(approvals, Permission.create, user, payload)
    records = [await run_triage(t, chain, store, kb, config) for t in tickets]
    return UploadResult(filename=filename, records=records)


@router.get("/tickets/{ticket_id}", response_model=TicketRecord)
async def get_ticket(
    ticket_id: str, store: StoreDep, people: PeopleDep, user: CurrentUser
) -> TicketRecord:
    return _visible(_load(store, ticket_id), people, user)


@router.post("/tickets/{ticket_id}/assign", response_model=TicketRecord)
async def assign(
    ticket_id: str, body: AssignIn, store: StoreDep, people: PeopleDep, user: CurrentUser
) -> TicketRecord:
    return _apply(store, ticket_id, lambda r: review.assign(r, body.owner, user), people, user)


@router.post("/tickets/{ticket_id}/team", response_model=TicketRecord)
async def move_team(
    ticket_id: str,
    body: TeamIn,
    store: StoreDep,
    people: PeopleDep,
    user: CurrentUser,
    config: ConfigDep,
    approvals: ApprovalsDep,
):
    """Move a ticket to another team. Its new team then decides who can see it."""
    require(user, Permission.move)
    _visible(_load(store, ticket_id), people, user)
    if config.access.needs_approval(user.role, Permission.move):
        return queue(approvals, Permission.move, user, {"team": body.team}, ticket_id)
    return _apply(store, ticket_id, lambda r: review.set_team(r, body.team, user), people, user)


@router.delete("/tickets/{ticket_id}", status_code=204, responses={202: {"description": "Waiting"}})
async def delete_ticket(
    ticket_id: str,
    store: StoreDep,
    people: PeopleDep,
    user: CurrentUser,
    config: ConfigDep,
    approvals: ApprovalsDep,
):
    """Archive a ticket: it leaves the lists but is kept. Admin approval may be needed first."""
    require(user, Permission.delete)
    _visible(_load(store, ticket_id), people, user)
    if config.access.needs_approval(user.role, Permission.delete):
        return queue(approvals, Permission.delete, user, {}, ticket_id)
    _apply(store, ticket_id, lambda r: review.archive(r, user), people, user)
    return None


@router.post("/tickets/{ticket_id}/restore", response_model=TicketRecord)
async def restore(
    ticket_id: str, store: StoreDep, people: PeopleDep, user: CurrentUser
) -> TicketRecord:
    """Bring an archived ticket back to the lists."""
    return _apply(store, ticket_id, lambda r: review.restore(r, user), people, user)


@router.post("/tickets/{ticket_id}/confirm", response_model=TicketRecord)
async def confirm(
    ticket_id: str, store: StoreDep, people: PeopleDep, user: CurrentUser
) -> TicketRecord:
    """Agree with the decision in force."""
    return _apply(store, ticket_id, lambda r: review.confirm(r, user), people, user)


@router.post("/tickets/{ticket_id}/override", response_model=TicketRecord)
async def override(
    ticket_id: str,
    body: OverrideIn,
    store: StoreDep,
    people: PeopleDep,
    user: CurrentUser,
    config: ConfigDep,
    approvals: ApprovalsDep,
):
    """Replace the agent's decision: send a reply instead, or hand it to a person."""
    require(user, Permission.override)
    _visible(_load(store, ticket_id), people, user)
    if config.access.needs_approval(user.role, Permission.override):
        payload = body.model_dump(mode="json")
        return queue(approvals, Permission.override, user, payload, ticket_id)
    return _apply(store, ticket_id, lambda r: review.override(r, body, user), people, user)


@router.post("/tickets/{ticket_id}/notes", response_model=TicketRecord)
async def add_note(
    ticket_id: str, body: NoteIn, store: StoreDep, people: PeopleDep, user: CurrentUser
) -> TicketRecord:
    return _apply(store, ticket_id, lambda r: review.add_note(r, body.text, user), people, user)


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketRecord)
async def resolve(
    ticket_id: str, store: StoreDep, people: PeopleDep, user: CurrentUser
) -> TicketRecord:
    return _apply(store, ticket_id, lambda r: review.resolve(r, user), people, user)
