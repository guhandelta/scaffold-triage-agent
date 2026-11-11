"""People, the teams they belong to, their role in each team, and a history of every change.

Stored in SQLite next to the tickets. Nothing is deleted: a person who leaves is deactivated, so
the history still shows who did what. A person can belong to several teams with a different role
in each.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

from app.config import get_settings
from app.schemas import Membership, Person, PersonEvent, Role, now


class PersonNotFound(KeyError):
    pass


class PeopleError(ValueError):
    """A change that does not make sense, such as adding someone to a team they are in already."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id     TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    email  TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS memberships (
    person_id TEXT NOT NULL REFERENCES people(id),
    team      TEXT NOT NULL,
    role      TEXT NOT NULL,
    PRIMARY KEY (person_id, team)
);
CREATE TABLE IF NOT EXISTS person_events (
    seq       INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL REFERENCES people(id),
    kind      TEXT NOT NULL,
    detail    TEXT NOT NULL,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL
);
"""


class PeopleStore:
    """Each change runs in one transaction, so a failed change leaves nothing half-written."""

    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._lock = Lock()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _person(self, person_id: str) -> Person:
        row = self._db.execute(
            "SELECT id, name, email, active FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        if row is None:
            raise PersonNotFound(person_id)
        rows = self._db.execute(
            "SELECT team, role FROM memberships WHERE person_id = ? ORDER BY team", (person_id,)
        ).fetchall()
        return Person(
            id=row[0],
            name=row[1],
            email=row[2],
            active=bool(row[3]),
            memberships=[Membership(team=team, role=Role(role)) for team, role in rows],
        )

    def _log(self, person_id: str, kind: str, detail: str, actor: str) -> None:
        self._db.execute(
            "INSERT INTO person_events (person_id, kind, detail, actor, at) VALUES (?, ?, ?, ?, ?)",
            (person_id, kind, detail, actor, now().isoformat()),
        )

    def _in_team(self, person: Person, team: str) -> Membership:
        for membership in person.memberships:
            if membership.team == team:
                return membership
        raise PeopleError(f"{person.name} is not in {team}")

    def list_people(self) -> list[Person]:
        with self._lock:
            ids = self._db.execute("SELECT id FROM people ORDER BY name, id").fetchall()
            return [self._person(row[0]) for row in ids]

    def get_person(self, person_id: str) -> Person:
        with self._lock:
            return self._person(person_id)

    def add_person(self, name: str, email: str | None, actor: str) -> Person:
        person_id = uuid.uuid4().hex[:12]
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO people (id, name, email, active) VALUES (?, ?, ?, 1)",
                (person_id, name, email),
            )
            self._log(person_id, "added", f"Added {name}", actor)
            return self._person(person_id)

    def add_membership(self, person_id: str, team: str, role: Role, actor: str) -> Person:
        with self._lock, self._db:
            person = self._person(person_id)
            if any(m.team == team for m in person.memberships):
                raise PeopleError(f"{person.name} is already in {team}")
            self._db.execute(
                "INSERT INTO memberships (person_id, team, role) VALUES (?, ?, ?)",
                (person_id, team, role.value),
            )
            self._log(person_id, "joined", f"Joined {team} as {role.value}", actor)
            return self._person(person_id)

    def change_role(self, person_id: str, team: str, role: Role, reason: str, actor: str) -> Person:
        with self._lock, self._db:
            person = self._person(person_id)
            current = self._in_team(person, team)
            if current.role == role:
                raise PeopleError(f"{person.name} is already {role.value} in {team}")
            self._db.execute(
                "UPDATE memberships SET role = ? WHERE person_id = ? AND team = ?",
                (role.value, person_id, team),
            )
            self._log(
                person_id,
                "role changed",
                f"{team}: {current.role.value} to {role.value}. Reason: {reason}",
                actor,
            )
            return self._person(person_id)

    def remove_membership(self, person_id: str, team: str, actor: str) -> Person:
        with self._lock, self._db:
            person = self._person(person_id)
            self._in_team(person, team)
            self._db.execute(
                "DELETE FROM memberships WHERE person_id = ? AND team = ?", (person_id, team)
            )
            self._log(person_id, "left", f"Left {team}", actor)
            return self._person(person_id)

    def set_active(self, person_id: str, active: bool, reason: str, actor: str) -> Person:
        with self._lock, self._db:
            person = self._person(person_id)
            if person.active == active:
                state = "active" if active else "inactive"
                raise PeopleError(f"{person.name} is already {state}")
            self._db.execute("UPDATE people SET active = ? WHERE id = ?", (int(active), person_id))
            kind = "reactivated" if active else "deactivated"
            self._log(person_id, kind, f"{kind.capitalize()}: {reason}", actor)
            return self._person(person_id)

    def history(self, person_id: str) -> list[PersonEvent]:
        with self._lock:
            self._person(person_id)
            rows = self._db.execute(
                "SELECT kind, detail, actor, at FROM person_events "
                "WHERE person_id = ? ORDER BY seq",
                (person_id,),
            ).fetchall()
        return [
            PersonEvent(kind=kind, detail=detail, actor=actor, at=datetime.fromisoformat(at))
            for kind, detail, actor, at in rows
        ]


_store: PeopleStore | None = None


def get_people_store() -> PeopleStore:
    """The app's people store, opened once on first use in the same database as the tickets."""
    global _store
    if _store is None:
        _store = PeopleStore(get_settings().database_path)
    return _store
