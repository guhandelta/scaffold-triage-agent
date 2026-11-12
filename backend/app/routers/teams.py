"""Teams: the admin creates them and decides their fields; members are added by hand or by file.

Only someone with manage_people (an admin by default) may change teams. Everyone may read them.
A team can be deleted only when nobody is in it and no ticket belongs to it.
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import ValidationError

from app.auth import CurrentUser, require
from app.deps import PeopleDep, StoreDep
from app.ingest import UploadError
from app.member_import import parse_members
from app.people import FieldError, Member, PeopleError, TeamNotFound
from app.schemas import (
    FieldsIn,
    ImportPlan,
    ImportRowPlan,
    MemberIn,
    Permission,
    Person,
    Role,
    Team,
    TeamCreateIn,
    TeamEvent,
)

router = APIRouter(prefix="/api/teams", tags=["teams"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="team not found")


def _conflict(e: PeopleError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(e))


@router.get("", response_model=list[Team])
async def list_teams(people: PeopleDep) -> list[Team]:
    return people.list_teams()


@router.post("", response_model=Team, status_code=201)
async def create_team(body: TeamCreateIn, people: PeopleDep, user: CurrentUser) -> Team:
    require(user, Permission.manage_people)
    try:
        return people.create_team(body.name, body.fields, user.name)
    except PeopleError as e:
        raise _conflict(e) from None


@router.get("/{name}", response_model=Team)
async def get_team(name: str, people: PeopleDep) -> Team:
    try:
        return people.get_team(name)
    except TeamNotFound:
        raise _not_found() from None


@router.put("/{name}/fields", response_model=Team)
async def set_fields(name: str, body: FieldsIn, people: PeopleDep, user: CurrentUser) -> Team:
    require(user, Permission.manage_people)
    try:
        return people.set_fields(name, body.fields, user.name)
    except TeamNotFound:
        raise _not_found() from None
    except PeopleError as e:
        raise _conflict(e) from None


@router.get("/{name}/history", response_model=list[TeamEvent])
async def team_history(name: str, people: PeopleDep) -> list[TeamEvent]:
    try:
        return people.team_history(name)
    except TeamNotFound:
        raise _not_found() from None


@router.delete("/{name}", status_code=204)
async def delete_team(name: str, people: PeopleDep, store: StoreDep, user: CurrentUser) -> None:
    require(user, Permission.manage_people)
    tickets = sum(1 for r in store.list_all() if r.team == name)
    try:
        people.delete_team(name, user.name, tickets)
    except TeamNotFound:
        raise _not_found() from None
    except PeopleError as e:
        raise _conflict(e) from None
    return None


@router.post("/{name}/members", response_model=Person, status_code=201)
async def add_member(name: str, body: MemberIn, people: PeopleDep, user: CurrentUser) -> Person:
    require(user, Permission.manage_people)
    try:
        return people.add_member(
            name, body.name, body.employee_id, body.email, body.role, body.details, user.name
        )
    except TeamNotFound:
        raise _not_found() from None
    except FieldError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    except PeopleError as e:
        raise _conflict(e) from None


def _member_from(raw: dict) -> tuple[MemberIn | None, list[str]]:
    if raw.get("problem"):
        return None, [raw["problem"]]
    try:
        body = MemberIn(
            name=raw["name"],
            email=raw["email"] or None,
            employee_id=raw["employee_id"] or None,
            role=raw["role"] or Role.agent,
            details=raw["details"],
        )
    except ValidationError as e:
        return None, [err["msg"].removeprefix("Value error, ") for err in e.errors()]
    return body, []


@router.post("/{name}/members/import", response_model=ImportPlan)
async def import_members(
    name: str,
    people: PeopleDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description=".csv, .md, .txt or .docx")],
    dry_run: Annotated[bool, Query(description="Show the plan only; write nothing")] = True,
) -> ImportPlan:
    """Read a member list and show what each row would do. Add them with dry_run=false.

    Nothing is added unless every row is valid, and then all rows are added together.
    """
    require(user, Permission.manage_people)
    filename = file.filename or "upload"
    try:
        raw_rows = parse_members(filename, await file.read())
    except UploadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    plans: list[ImportRowPlan] = []
    valid_rows: list[ImportRowPlan] = []
    members: list[Member] = []
    seen: set[str] = set()
    for raw in raw_rows:
        body, problems = _member_from(raw)
        # A row is the same person as another if they share an employee ID or an email. A row
        # with neither is matched by name, so two of them with one name are a duplicate too.
        keys: set[str] = set()
        if body is not None:
            if body.employee_id:
                keys.add(f"id:{body.employee_id}")
            if body.email:
                keys.add(f"email:{body.email.lower()}")
            if not keys:
                keys.add(f"name:{body.name.lower()}")
            if keys & seen:
                problems.append("appears twice in this file")
            seen |= keys
        row = ImportRowPlan(
            line=raw["line"],
            name=raw["name"],
            email=raw["email"] or None,
            employee_id=raw["employee_id"] or None,
            role=body.role if body else None,
            action="error",
            problems=problems,
        )
        if body is None or problems:
            plans.append(row)
            continue
        valid_rows.append(row.model_copy(update={"action": ""}))
        members.append(Member(body.name, body.email, body.employee_id, body.role, body.details))

    try:
        checked = people.plan_import(name, valid_rows, members)
    except TeamNotFound:
        raise _not_found() from None
    rows = sorted([*plans, *checked], key=lambda r: r.line)
    can_commit = bool(rows) and all(r.action != "error" for r in rows)

    if dry_run:
        return ImportPlan(team=name, committed=False, can_commit=can_commit, rows=rows)
    if not can_commit:
        raise HTTPException(
            status_code=422, detail="fix the rows marked as errors, then import again"
        )
    try:
        people.import_members(name, members, user.name)
    except PeopleError as e:
        raise _conflict(e) from None
    return ImportPlan(team=name, committed=True, can_commit=True, rows=rows)
