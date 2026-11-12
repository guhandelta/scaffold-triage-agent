"""People, the teams they belong to, their role and details in each team, and every change.

Stored in SQLite next to the tickets. Nothing is deleted: a person who leaves is deactivated, so
the history still shows who did what. A person can belong to several teams with a different role
in each. Teams have admin-defined fields; each member's values for them are checked against those
fields. Every change to a team is kept in its history too.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.config import get_settings
from app.schemas import (
    ImportRowPlan,
    Membership,
    Person,
    PersonEvent,
    Role,
    Team,
    TeamEvent,
    TeamField,
    now,
)


class PersonNotFound(KeyError):
    pass


class TeamNotFound(KeyError):
    pass


class PeopleError(ValueError):
    """A change that does not make sense, such as adding someone to a team they are in already."""


class FieldError(PeopleError):
    """A member's value for a team field is not allowed, such as a date that is not a date."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    employee_id TEXT
);
CREATE TABLE IF NOT EXISTS memberships (
    person_id TEXT NOT NULL REFERENCES people(id),
    team      TEXT NOT NULL,
    role      TEXT NOT NULL,
    PRIMARY KEY (person_id, team)
);
CREATE TABLE IF NOT EXISTS member_fields (
    person_id TEXT NOT NULL REFERENCES people(id),
    team      TEXT NOT NULL,
    key       TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (person_id, team, key)
);
CREATE TABLE IF NOT EXISTS person_events (
    seq       INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL REFERENCES people(id),
    kind      TEXT NOT NULL,
    detail    TEXT NOT NULL,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS teams (
    name       TEXT PRIMARY KEY,
    fields     TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS team_events (
    seq   INTEGER PRIMARY KEY AUTOINCREMENT,
    team  TEXT NOT NULL,
    kind  TEXT NOT NULL,
    detail TEXT NOT NULL,
    actor TEXT NOT NULL,
    at    TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Member:
    name: str
    email: str | None
    employee_id: str | None
    role: Role
    details: dict[str, str]


class PeopleStore:
    """Each change runs in one transaction, so a failed change leaves nothing half-written."""

    def __init__(self, path: str) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._migrate()
        self._lock = Lock()

    def _migrate(self) -> None:
        # Databases made before employee IDs existed get the column added in place.
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(people)")}
        if "employee_id" not in columns:
            self._db.execute("ALTER TABLE people ADD COLUMN employee_id TEXT")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Reading

    def _person(self, person_id: str) -> Person:
        row = self._db.execute(
            "SELECT id, name, email, active, employee_id FROM people WHERE id = ?", (person_id,)
        ).fetchone()
        if row is None:
            raise PersonNotFound(person_id)
        rows = self._db.execute(
            "SELECT team, role FROM memberships WHERE person_id = ? ORDER BY team", (person_id,)
        ).fetchall()
        memberships = [
            Membership(team=team, role=Role(role), details=self._details(person_id, team))
            for team, role in rows
        ]
        return Person(
            id=row[0],
            name=row[1],
            email=row[2],
            active=bool(row[3]),
            employee_id=row[4],
            memberships=memberships,
        )

    def _details(self, person_id: str, team: str) -> dict[str, str]:
        rows = self._db.execute(
            "SELECT key, value FROM member_fields WHERE person_id = ? AND team = ?",
            (person_id, team),
        ).fetchall()
        return dict(rows)

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

    def history(self, person_id: str) -> list[PersonEvent]:
        with self._lock:
            self._person(person_id)
            rows = self._db.execute(
                "SELECT kind, detail, actor, at FROM person_events "
                "WHERE person_id = ? ORDER BY seq",
                (person_id,),
            ).fetchall()
        return [
            PersonEvent(kind=kind, detail=detail, actor=actor, at=dt.datetime.fromisoformat(at))
            for kind, detail, actor, at in rows
        ]

    def teams_of(self, name: str) -> set[str]:
        """Teams of the active person with this name. Anyone not in the directory has none."""
        with self._lock:
            rows = self._db.execute(
                "SELECT m.team FROM people p JOIN memberships m ON m.person_id = p.id "
                "WHERE lower(p.name) = lower(?) AND p.active = 1",
                (name,),
            ).fetchall()
        return {team for (team,) in rows}

    # People

    def add_person(
        self, name: str, email: str | None, actor: str, employee_id: str | None = None
    ) -> Person:
        person_id = uuid.uuid4().hex[:12]
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO people (id, name, email, active, employee_id) VALUES (?, ?, ?, 1, ?)",
                (person_id, name, email, employee_id),
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
            self._db.execute(
                "DELETE FROM member_fields WHERE person_id = ? AND team = ?", (person_id, team)
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

    # Teams

    def _team_row(self, name: str) -> Team:
        row = self._db.execute(
            "SELECT name, fields, created_at, created_by FROM teams WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise TeamNotFound(name)
        return Team(
            name=row[0],
            fields=[TeamField(**f) for f in json.loads(row[1])],
            created_at=dt.datetime.fromisoformat(row[2]),
            created_by=row[3],
        )

    def _team_log(self, team: str, kind: str, detail: str, actor: str) -> None:
        self._db.execute(
            "INSERT INTO team_events (team, kind, detail, actor, at) VALUES (?, ?, ?, ?, ?)",
            (team, kind, detail, actor, now().isoformat()),
        )

    def list_teams(self) -> list[Team]:
        with self._lock:
            names = self._db.execute("SELECT name FROM teams ORDER BY name").fetchall()
            return [self._team_row(name) for (name,) in names]

    def get_team(self, name: str) -> Team:
        with self._lock:
            return self._team_row(name)

    def team_history(self, name: str) -> list[TeamEvent]:
        """Every change to the team, kept even after the team is deleted."""
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, detail, actor, at FROM team_events WHERE team = ? ORDER BY seq",
                (name,),
            ).fetchall()
        if not rows:
            raise TeamNotFound(name)
        return [
            TeamEvent(kind=kind, detail=detail, actor=actor, at=dt.datetime.fromisoformat(at))
            for kind, detail, actor, at in rows
        ]

    def create_team(self, name: str, fields: list[TeamField], actor: str) -> Team:
        with self._lock, self._db:
            exists = self._db.execute("SELECT 1 FROM teams WHERE name = ?", (name,)).fetchone()
            if exists:
                raise PeopleError(f"team {name} already exists")
            _check_fields(fields)
            self._db.execute(
                "INSERT INTO teams (name, fields, created_at, created_by) VALUES (?, ?, ?, ?)",
                (name, _dump(fields), now().isoformat(), actor),
            )
            self._team_log(name, "created", f"Created {name}", actor)
            return self._team_row(name)

    def set_fields(self, name: str, fields: list[TeamField], actor: str) -> Team:
        """Replace the team's fields. A field with values on any member cannot be removed."""
        with self._lock, self._db:
            before = {f.key: f for f in self._team_row(name).fields}
            _check_fields(fields)
            after = {f.key: f for f in fields}
            for key in before.keys() - after.keys():
                in_use = self._db.execute(
                    "SELECT 1 FROM member_fields WHERE team = ? AND key = ?", (name, key)
                ).fetchone()
                if in_use:
                    raise PeopleError(f"field {key} has values on members; clear them first")
            for key, field in after.items():
                if key not in before:
                    self._team_log(
                        name, "field added", f"Added {field.label} ({field.type.value})", actor
                    )
                elif before[key] != field:
                    self._team_log(name, "field changed", f"Changed {field.label}", actor)
            for key in before.keys() - after.keys():
                self._team_log(name, "field removed", f"Removed {before[key].label}", actor)
            self._db.execute("UPDATE teams SET fields = ? WHERE name = ?", (_dump(fields), name))
            return self._team_row(name)

    def delete_team(self, name: str, actor: str, tickets: int) -> None:
        """Remove a team that no one is in and no ticket belongs to. Its history is kept."""
        with self._lock, self._db:
            self._team_row(name)
            members = self._db.execute(
                "SELECT COUNT(*) FROM memberships WHERE team = ?", (name,)
            ).fetchone()[0]
            if members:
                raise PeopleError(f"{name} still has {members} member(s)")
            if tickets:
                raise PeopleError(f"{name} still has {tickets} ticket(s)")
            self._db.execute("DELETE FROM teams WHERE name = ?", (name,))
            self._team_log(name, "deleted", f"Deleted {name}", actor)

    # Adding people to teams, with their details

    def _match(
        self, employee_id: str | None, email: str | None, name: str
    ) -> tuple[str, str | None]:
        """Find the existing person a row refers to. Returns ("matched", id), ("new", None) or
        ("ambiguous", None). A name alone never links to someone, because two people can share one.
        """
        if employee_id or email:
            if employee_id:
                row = self._db.execute(
                    "SELECT id FROM people WHERE employee_id = ?", (employee_id,)
                ).fetchone()
                if row:
                    return "matched", row[0]
            if email:
                row = self._db.execute(
                    "SELECT id FROM people WHERE lower(email) = lower(?)", (email,)
                ).fetchone()
                if row:
                    return "matched", row[0]
            return "new", None
        same = self._db.execute(
            "SELECT COUNT(*) FROM people WHERE lower(name) = lower(?)", (name,)
        ).fetchone()[0]
        return ("ambiguous", None) if same else ("new", None)

    def _validate_details(self, team: str, details: dict[str, str]) -> dict[str, str]:
        fields = self._team_row(team).fields
        return validate_details(fields, details)

    def _add_member_unlocked(
        self,
        team: str,
        member: Member,
        actor: str,
    ) -> Person:
        details = self._validate_details(team, member.details)
        kind, person_id = self._match(member.employee_id, member.email, member.name)
        if kind == "ambiguous":
            raise PeopleError(
                f"more than one person is called {member.name}; give an employee ID or email"
            )
        if kind == "new":
            person_id = uuid.uuid4().hex[:12]
            self._db.execute(
                "INSERT INTO people (id, name, email, active, employee_id) VALUES (?, ?, ?, 1, ?)",
                (person_id, member.name, member.email, member.employee_id),
            )
            self._log(person_id, "added", f"Added {member.name}", actor)
        person = self._person(person_id)
        if not person.active:
            raise PeopleError(f"{person.name} is inactive")
        if any(m.team == team for m in person.memberships):
            raise PeopleError(f"{person.name} is already in {team}")
        self._db.execute(
            "INSERT INTO memberships (person_id, team, role) VALUES (?, ?, ?)",
            (person_id, team, member.role.value),
        )
        self._log(person_id, "joined", f"Joined {team} as {member.role.value}", actor)
        for key, value in details.items():
            self._db.execute(
                "INSERT INTO member_fields (person_id, team, key, value) VALUES (?, ?, ?, ?)",
                (person_id, team, key, value),
            )
        if details:
            self._log(person_id, "details", f"{team}: " + ", ".join(sorted(details)), actor)
        return self._person(person_id)

    def add_member(
        self,
        team: str,
        name: str,
        employee_id: str | None,
        email: str | None,
        role: Role,
        details: dict[str, str],
        actor: str,
    ) -> Person:
        with self._lock, self._db:
            self._team_row(team)
            return self._add_member_unlocked(
                team, Member(name, email, employee_id, role, details), actor
            )

    def plan_import(self, team: str, rows: list[ImportRowPlan], members: list[Member]) -> list:
        """Say what each row would do, without writing anything."""
        plans = []
        with self._lock:
            self._team_row(team)
            for row, member in zip(rows, members, strict=True):
                problems: list[str] = []
                try:
                    self._validate_details(team, member.details)
                except PeopleError as e:
                    problems.append(str(e))
                action = "error"
                kind, person_id = self._match(member.employee_id, member.email, member.name)
                if kind == "ambiguous":
                    problems.append(
                        f"more than one person is called {member.name}; "
                        "give an employee ID or email"
                    )
                elif kind == "matched":
                    person = self._person(person_id)
                    if not person.active:
                        problems.append(f"{person.name} is inactive")
                    elif any(m.team == team for m in person.memberships):
                        problems.append(f"{person.name} is already in {team}")
                    else:
                        action = "link"
                else:
                    action = "add"
                if problems:
                    action = "error"
                plans.append(row.model_copy(update={"action": action, "problems": problems}))
        return plans

    def import_members(self, team: str, members: list[Member], actor: str) -> int:
        """Add every member in one transaction: either all of them are added or none is."""
        with self._lock, self._db:
            self._team_row(team)
            for member in members:
                self._add_member_unlocked(team, member, actor)
        return len(members)


def validate_details(fields: list[TeamField], details: dict[str, str]) -> dict[str, str]:
    """Check a member's values against the team's fields. Returns only the non-empty values."""
    known = {f.key: f for f in fields}
    unknown = sorted(set(details) - set(known))
    if unknown:
        raise FieldError(f"unknown field(s): {', '.join(unknown)}")
    cleaned: dict[str, str] = {}
    for field in fields:
        value = (details.get(field.key) or "").strip()
        if not value:
            if field.required:
                raise FieldError(f"{field.label} is required")
            continue
        if field.type == "date":
            try:
                dt.date.fromisoformat(value)
            except ValueError:
                raise FieldError(f"{field.label} must be a date like 2026-11-30") from None
        elif field.type == "choice" and value not in field.choices:
            raise FieldError(f"{field.label} must be one of: {', '.join(field.choices)}")
        elif len(value) > 500:
            raise FieldError(f"{field.label} is too long")
        cleaned[field.key] = value
    return cleaned


def _check_fields(fields: list[TeamField]) -> None:
    keys = [f.key for f in fields]
    if len(keys) != len(set(keys)):
        raise PeopleError("each field needs a unique key")


def _dump(fields: list[TeamField]) -> str:
    return json.dumps([f.model_dump(mode="json") for f in fields])


_store: PeopleStore | None = None


def get_people_store() -> PeopleStore:
    """The app's people store, opened once on first use in the same database as the tickets."""
    global _store
    if _store is None:
        _store = PeopleStore(get_settings().database_path)
    return _store
