"""Who is in which team, with what role, and how that changed.

Only someone with `manage_people` (an admin, by default) can change people. Every change is kept
in the person's history. When a person is deactivated, the open tickets they owned go back to the
queue, so nothing stays with someone who has left.
"""

from collections.abc import Callable

from fastapi import APIRouter, HTTPException

from app.auth import CurrentUser, require
from app.deps import PeopleDep, StoreDep
from app.people import PeopleError, PersonNotFound
from app.schemas import (
    HistoryEvent,
    MembershipIn,
    Permission,
    Person,
    PersonEvent,
    PersonIn,
    RoleChangeIn,
    StatusIn,
    TicketStatus,
)
from app.store import TicketStore

router = APIRouter(prefix="/api/people", tags=["people"])


def _check[T](call: Callable[[], T]) -> T:
    try:
        return call()
    except PersonNotFound:
        raise HTTPException(status_code=404, detail="person not found") from None
    except PeopleError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


def release_tickets(store: TicketStore, name: str, actor: str) -> None:
    """Hand every open ticket the person owned back to the queue, with a history entry."""
    for record in store.list_all():
        if record.owner == name and record.status != TicketStatus.resolved:
            event = HistoryEvent(
                kind="released", detail=f"{name} left, so it is back in the queue", actor=actor
            )
            store.save(
                record.model_copy(update={"owner": None, "history": [*record.history, event]})
            )


@router.get("", response_model=list[Person])
async def list_people(people: PeopleDep) -> list[Person]:
    """Everyone, with their teams and roles."""
    return people.list_people()


@router.post("", response_model=Person, status_code=201)
async def add_person(body: PersonIn, people: PeopleDep, user: CurrentUser) -> Person:
    require(user, Permission.manage_people)
    return people.add_person(body.name, body.email, user.name)


@router.get("/{person_id}", response_model=Person)
async def get_person(person_id: str, people: PeopleDep) -> Person:
    return _check(lambda: people.get_person(person_id))


@router.get("/{person_id}/history", response_model=list[PersonEvent])
async def person_history(person_id: str, people: PeopleDep) -> list[PersonEvent]:
    return _check(lambda: people.history(person_id))


@router.post("/{person_id}/memberships", response_model=Person)
async def add_membership(
    person_id: str, body: MembershipIn, people: PeopleDep, user: CurrentUser
) -> Person:
    require(user, Permission.manage_people)
    return _check(lambda: people.add_membership(person_id, body.team, body.role, user.name))


@router.patch("/{person_id}/memberships/{team}", response_model=Person)
async def change_role(
    person_id: str, team: str, body: RoleChangeIn, people: PeopleDep, user: CurrentUser
) -> Person:
    require(user, Permission.manage_people)
    return _check(
        lambda: people.change_role(
            person_id, team.strip().lower(), body.role, body.reason, user.name
        )
    )


@router.delete("/{person_id}/memberships/{team}", response_model=Person)
async def remove_membership(
    person_id: str, team: str, people: PeopleDep, user: CurrentUser
) -> Person:
    require(user, Permission.manage_people)
    return _check(lambda: people.remove_membership(person_id, team.strip().lower(), user.name))


@router.post("/{person_id}/status", response_model=Person)
async def set_status(
    person_id: str, body: StatusIn, people: PeopleDep, store: StoreDep, user: CurrentUser
) -> Person:
    """Deactivate someone who has left, or reactivate them. Deactivating releases their tickets."""
    require(user, Permission.manage_people)
    person = _check(lambda: people.set_active(person_id, body.active, body.reason, user.name))
    if not body.active:
        release_tickets(store, person.name, user.name)
    return person
