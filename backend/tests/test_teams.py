"""Teams with admin-defined fields, members added by hand or from a file, and the team history."""

import io
import sqlite3

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.member_import import parse_members
from app.people import FieldError, Member, PeopleError, PeopleStore, TeamNotFound, validate_details
from app.schemas import Action, FieldType, Role, TeamField
from tests.test_store import _record

client = TestClient(app)
ADMIN = {"X-User-Name": "Admin", "X-User-Role": "admin"}
REVIEWER = {"X-User-Name": "Lee", "X-User-Role": "reviewer"}
START = {"key": "start_date", "label": "Start date", "type": "date"}
LEVEL = {
    "key": "level",
    "label": "Level",
    "type": "choice",
    "choices": ["junior", "senior"],
    "required": True,
}


def _field(**kwargs) -> TeamField:
    return TeamField(**{"key": "x", "label": "X", **kwargs})


def _team(name: str = "billing", fields=None) -> dict:
    return client.post(
        "/api/teams", json={"name": name, "fields": fields or []}, headers=ADMIN
    ).json()


# Fields and validation


def test_a_choice_field_needs_choices_and_others_have_none():
    with pytest.raises(ValueError):
        _field(type="choice")
    with pytest.raises(ValueError):
        _field(type="text", choices=["a"])
    assert _field(type="choice", choices=["a"]).type == FieldType.choice


def test_values_are_checked_against_their_field_type():
    fields = [
        _field(key="start_date", type="date"),
        _field(key="level", type="choice", choices=["a", "b"]),
        _field(key="note"),
    ]
    cleaned = validate_details(fields, {"start_date": "2026-11-30", "level": "a", "note": "  "})
    assert cleaned == {"start_date": "2026-11-30", "level": "a"}
    with pytest.raises(FieldError, match="a date"):
        validate_details(fields, {"start_date": "next week"})
    with pytest.raises(FieldError, match="one of"):
        validate_details(fields, {"level": "c"})
    with pytest.raises(FieldError, match="too long"):
        validate_details(fields, {"note": "x" * 501})
    with pytest.raises(FieldError, match="unknown field"):
        validate_details(fields, {"mystery": "x"})


def test_a_required_field_must_have_a_value():
    fields = [_field(key="level", label="Level", type="choice", choices=["a"], required=True)]
    with pytest.raises(FieldError, match="Level is required"):
        validate_details(fields, {})


# The store: teams and their history


def test_a_team_is_created_listed_and_read_back(people_store: PeopleStore):
    people_store.create_team("billing", [_field(key="level", label="Level", type="text")], "Admin")
    assert [t.name for t in people_store.list_teams()] == ["billing"]
    assert people_store.get_team("billing").fields[0].key == "level"
    with pytest.raises(TeamNotFound):
        people_store.get_team("nope")


def test_a_team_name_can_be_used_once(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    with pytest.raises(PeopleError, match="already exists"):
        people_store.create_team("billing", [], "Admin")


def test_field_keys_must_be_unique(people_store: PeopleStore):
    with pytest.raises(PeopleError, match="unique key"):
        people_store.create_team("billing", [_field(key="a"), _field(key="a")], "Admin")


def test_the_team_history_records_each_field_change(people_store: PeopleStore):
    people_store.create_team("billing", [_field(key="a", label="A")], "Admin")
    people_store.set_fields(
        "billing", [_field(key="a", label="Alpha"), _field(key="b", label="B")], "Admin"
    )
    people_store.set_fields("billing", [_field(key="a", label="Alpha")], "Admin")
    kinds = [e.kind for e in people_store.team_history("billing")]
    assert kinds == ["created", "field changed", "field added", "field removed"]
    assert people_store.team_history("billing")[1].detail == "Changed Alpha"


def test_a_field_with_values_cannot_be_removed(people_store: PeopleStore):
    people_store.create_team("billing", [_field(key="a", label="A")], "Admin")
    people_store.add_member("billing", "Ana", None, None, Role.agent, {"a": "v"}, "Admin")
    with pytest.raises(PeopleError, match="clear them first"):
        people_store.set_fields("billing", [], "Admin")


def test_a_team_with_members_or_tickets_cannot_be_deleted(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    ana = people_store.add_member("billing", "Ana", None, None, Role.agent, {}, "Admin")
    with pytest.raises(PeopleError, match="member"):
        people_store.delete_team("billing", "Admin", 0)
    people_store.remove_membership(ana.id, "billing", "Admin")
    with pytest.raises(PeopleError, match="ticket"):
        people_store.delete_team("billing", "Admin", 2)


def test_an_empty_team_is_deleted_and_its_history_kept(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    people_store.delete_team("billing", "Admin", 0)
    with pytest.raises(TeamNotFound):
        people_store.get_team("billing")
    assert people_store.team_history("billing")[-1].kind == "deleted"


def test_deleting_an_unknown_team_is_refused(people_store: PeopleStore):
    with pytest.raises(TeamNotFound):
        people_store.delete_team("nope", "Admin", 0)


# The store: adding members


def test_a_new_member_is_added_with_their_details(people_store: PeopleStore):
    people_store.create_team("billing", [_field(**START), _field(**LEVEL)], "Admin")
    person = people_store.add_member(
        "billing",
        "Ana",
        "E-1",
        "ana@example.com",
        Role.agent,
        {"start_date": "2026-11-30", "level": "junior"},
        "Admin",
    )
    assert person.employee_id == "E-1"
    assert person.memberships[0].details == {"start_date": "2026-11-30", "level": "junior"}
    assert people_store.history(person.id)[-1].kind == "details"


def test_an_employee_id_or_email_links_to_the_existing_person(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    ana = people_store.add_person("Ana", "ana@example.com", "Admin", employee_id="E-1")
    by_id = people_store.add_member("billing", "Ana B", "E-1", None, Role.agent, {}, "Admin")
    assert by_id.id == ana.id
    people_store.create_team("support", [], "Admin")
    by_email = people_store.add_member(
        "support", "A", None, "ANA@example.com", Role.agent, {}, "Admin"
    )
    assert by_email.id == ana.id


def test_a_name_alone_never_links_to_someone_and_is_refused_when_taken(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    people_store.add_person("Priya", None, "Admin")
    with pytest.raises(PeopleError, match="more than one person"):
        people_store.add_member("billing", "Priya", None, None, Role.agent, {}, "Admin")


def test_a_new_name_is_added_as_a_new_person(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    assert (
        people_store.add_member("billing", "Zed", None, None, Role.agent, {}, "Admin").name == "Zed"
    )


def test_the_same_person_cannot_join_a_team_twice_or_while_inactive(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    ana = people_store.add_person("Ana", None, "Admin", employee_id="E-1")
    people_store.add_member("billing", "Ana", "E-1", None, Role.agent, {}, "Admin")
    with pytest.raises(PeopleError, match="already in billing"):
        people_store.add_member("billing", "Ana", "E-1", None, Role.agent, {}, "Admin")
    people_store.set_active(ana.id, False, "Left", "Admin")
    people_store.create_team("support", [], "Admin")
    with pytest.raises(PeopleError, match="inactive"):
        people_store.add_member("support", "Ana", "E-1", None, Role.agent, {}, "Admin")


def test_a_bad_field_value_stops_the_add(people_store: PeopleStore):
    people_store.create_team("billing", [_field(**START)], "Admin")
    with pytest.raises(FieldError):
        people_store.add_member(
            "billing", "Ana", None, None, Role.agent, {"start_date": "soon"}, "Admin"
        )
    assert people_store.list_people() == []


def test_adding_to_an_unknown_team_is_refused(people_store: PeopleStore):
    with pytest.raises(TeamNotFound):
        people_store.add_member("nope", "Ana", None, None, Role.agent, {}, "Admin")


def test_removing_someone_from_a_team_removes_their_details(people_store: PeopleStore):
    people_store.create_team("billing", [_field(**START)], "Admin")
    ana = people_store.add_member(
        "billing", "Ana", None, None, Role.agent, {"start_date": "2026-11-30"}, "Admin"
    )
    left = people_store.remove_membership(ana.id, "billing", "Admin")
    assert left.memberships == []
    people_store.set_fields("billing", [], "Admin")  # no values left, so the field can go


# The store: imports


def test_an_import_plan_shows_what_each_row_would_do(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    people_store.add_person("Ana", None, "Admin", employee_id="E-1")
    from app.schemas import ImportRowPlan

    rows = [
        ImportRowPlan(line=2, name="Ana", employee_id="E-1", action="", problems=[]),
        ImportRowPlan(line=3, name="Zed", action="", problems=[]),
    ]
    members = [
        Member("Ana", None, "E-1", Role.agent, {}),
        Member("Zed", None, None, Role.agent, {}),
    ]
    plan = people_store.plan_import("billing", rows, members)
    assert [p.action for p in plan] == ["link", "add"]


def test_an_import_is_all_or_nothing(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    members = [
        Member("Ana", None, None, Role.agent, {}),
        Member("Ana", None, None, Role.agent, {"nope": "x"}),
    ]
    with pytest.raises(FieldError):
        people_store.import_members("billing", members, "Admin")
    assert people_store.list_people() == []


def test_an_import_adds_everyone_when_all_are_valid(people_store: PeopleStore):
    people_store.create_team("billing", [], "Admin")
    count = people_store.import_members(
        "billing",
        [Member("Ana", None, None, Role.agent, {}), Member("Ben", None, None, Role.agent, {})],
        "Admin",
    )
    assert count == 2
    assert len(people_store.list_people()) == 2


def test_an_older_database_gains_the_employee_id_column(tmp_path):
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE people (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT, "
        "active INTEGER NOT NULL DEFAULT 1)"
    )
    old.execute("INSERT INTO people (id, name, active) VALUES ('p1', 'Ana', 1)")
    old.commit()
    old.close()
    store = PeopleStore(path)
    try:
        assert store.get_person("p1").employee_id is None
    finally:
        store.close()


# The API


def test_only_admins_change_teams(people_store):
    assert client.post("/api/teams", json={"name": "billing"}, headers=REVIEWER).status_code == 403
    assert (
        client.put("/api/teams/billing/fields", json={"fields": []}, headers=REVIEWER).status_code
        == 403
    )
    assert client.delete("/api/teams/billing", headers=REVIEWER).status_code == 403
    assert (
        client.post("/api/teams/billing/members", json={"name": "A"}, headers=REVIEWER).status_code
        == 403
    )


def test_anyone_can_read_teams(people_store):
    _team("billing", [START])
    assert [t["name"] for t in client.get("/api/teams", headers=REVIEWER).json()] == ["billing"]
    assert client.get("/api/teams/billing").json()["fields"][0]["key"] == "start_date"


def test_the_team_api_creates_updates_and_reports_history(people_store):
    created = _team("billing", [START])
    assert created["created_by"] == "Admin"
    again = client.post("/api/teams", json={"name": "billing"}, headers=ADMIN)
    assert again.status_code == 409
    updated = client.put(
        "/api/teams/billing/fields", json={"fields": [START, LEVEL]}, headers=ADMIN
    )
    assert updated.status_code == 200
    kinds = [e["kind"] for e in client.get("/api/teams/billing/history").json()]
    assert kinds == ["created", "field added"]


def test_bad_field_definitions_are_rejected(people_store):
    bad = {"key": "level", "label": "Level", "type": "choice"}
    assert (
        client.post(
            "/api/teams", json={"name": "billing", "fields": [bad]}, headers=ADMIN
        ).status_code
        == 422
    )
    assert client.post("/api/teams", json={"name": "bad name"}, headers=ADMIN).status_code == 422


def test_unknown_teams_are_404(people_store):
    assert client.get("/api/teams/nope").status_code == 404
    assert client.get("/api/teams/nope/history").status_code == 404
    assert (
        client.put("/api/teams/nope/fields", json={"fields": []}, headers=ADMIN).status_code == 404
    )
    assert client.delete("/api/teams/nope", headers=ADMIN).status_code == 404
    assert (
        client.post("/api/teams/nope/members", json={"name": "A"}, headers=ADMIN).status_code == 404
    )


def test_a_field_with_values_cannot_be_removed_through_the_api(people_store):
    _team("billing", [START])
    client.post(
        "/api/teams/billing/members",
        json={"name": "Ana", "details": {"start_date": "2026-11-30"}},
        headers=ADMIN,
    )
    r = client.put("/api/teams/billing/fields", json={"fields": []}, headers=ADMIN)
    assert r.status_code == 409


def test_a_member_is_added_by_hand_with_details(people_store):
    _team("billing", [START, LEVEL])
    r = client.post(
        "/api/teams/billing/members",
        json={
            "name": "Ana",
            "employee_id": "E-1",
            "email": "ana@example.com",
            "role": "reviewer",
            "details": {"start_date": "2026-11-30", "level": "senior"},
        },
        headers=ADMIN,
    )
    assert r.status_code == 201
    assert r.json()["memberships"][0]["details"]["level"] == "senior"


def test_a_bad_detail_is_422_and_a_clash_is_409(people_store):
    _team("billing", [START, LEVEL])
    bad = client.post(
        "/api/teams/billing/members",
        json={"name": "Ana", "details": {"start_date": "soon", "level": "senior"}},
        headers=ADMIN,
    )
    assert bad.status_code == 422
    client.post(
        "/api/teams/billing/members",
        json={"name": "Ana", "details": {"level": "senior"}},
        headers=ADMIN,
    )
    clash = client.post(
        "/api/teams/billing/members",
        json={"name": "Ana", "details": {"level": "junior"}},
        headers=ADMIN,
    )
    assert clash.status_code == 409


def test_a_team_in_use_by_tickets_cannot_be_deleted_and_an_empty_one_can(people_store):
    _team("billing")
    _team("support")
    client.post("/api/teams/billing/members", json={"name": "Ana"}, headers=ADMIN)
    assert client.delete("/api/teams/billing", headers=ADMIN).status_code == 409
    assert client.delete("/api/teams/support", headers=ADMIN).status_code == 204
    assert client.get("/api/teams/support").status_code == 404


def test_a_team_with_tickets_cannot_be_deleted(people_store, store):
    _team("billing")
    store.save(_record("t1", Action.escalate).model_copy(update={"team": "billing"}))
    blocked = client.delete("/api/teams/billing", headers=ADMIN)
    assert blocked.status_code == 409
    assert "1 ticket" in blocked.json()["detail"]


# The API: importing members from a file


def _upload(name: str, data: bytes, dry_run: bool = True):
    return client.post(
        f"/api/teams/billing/members/import?dry_run={'true' if dry_run else 'false'}",
        files={"file": (name, data, "text/plain")},
        headers=ADMIN,
    )


def _docx(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_a_csv_import_is_previewed_then_committed(people_store):
    _team("billing", [START])
    csv = b"name,email,employee id,role,start_date\nAna,ana@example.com,E-1,reviewer,2026-11-30\n"
    preview = _upload("members.csv", csv)
    assert preview.status_code == 200
    body = preview.json()
    assert body["committed"] is False and body["can_commit"] is True
    assert body["rows"][0]["action"] == "add"
    assert client.get("/api/people").json() == []

    committed = _upload("members.csv", csv, dry_run=False).json()
    assert committed["committed"] is True
    ana = client.get("/api/people").json()[0]
    assert ana["employee_id"] == "E-1"
    assert ana["memberships"][0] == {
        "team": "billing",
        "role": "reviewer",
        "details": {"start_date": "2026-11-30"},
    }


def test_a_text_import_reads_one_member_per_line(people_store):
    _team("billing")
    text = b"# name, email, employee id, role\nAna, ana@example.com, E-1, agent\n\nBen\n"
    body = _upload("members.txt", text).json()
    assert [r["action"] for r in body["rows"]] == ["add", "add"]
    assert body["rows"][1]["role"] is None or body["rows"][1]["role"] == "agent"


def test_a_docx_import_is_read(people_store):
    _team("billing")
    body = client.post(
        "/api/teams/billing/members/import",
        files={
            "file": (
                "members.docx",
                _docx("Ana, ana@example.com, E-1, agent"),
                "application/octet-stream",
            )
        },
        headers=ADMIN,
    ).json()
    assert body["rows"][0]["action"] == "add"


def test_bad_rows_are_marked_and_block_the_import(people_store):
    _team("billing")
    text = (
        b"Ana, not-an-email\n"
        b"Ben, ben@example.com, , teacher\n"
        b"Cy, cy@example.com, E-3, agent, extra\n"
        b"Ana, ana@example.com\n"
    )
    body = _upload("members.txt", text).json()
    assert body["can_commit"] is False
    problems = {r["line"]: r["problems"] for r in body["rows"]}
    assert problems[1] and problems[2] and problems[3]
    assert _upload("members.txt", text, dry_run=False).status_code == 422
    assert client.get("/api/people").json() == []


def test_a_row_repeated_in_the_file_is_flagged(people_store):
    _team("billing")
    text = b"Ana, ana@example.com, E-1, agent\nAnna, ana@example.com, E-1, agent\n"
    body = _upload("members.txt", text).json()
    assert body["rows"][1]["problems"] == ["appears twice in this file"]


def test_a_name_that_matches_two_people_needs_an_id(people_store):
    _team("billing")
    people_store.add_person("Priya", None, "Admin")
    people_store.add_person("Priya", None, "Admin")
    body = _upload("members.txt", b"Priya\n").json()
    assert body["can_commit"] is False
    assert "more than one person" in body["rows"][0]["problems"][0]


def test_an_import_into_an_unknown_team_is_404(people_store):
    r = client.post(
        "/api/teams/nope/members/import",
        files={"file": ("m.txt", b"Ana\n", "text/plain")},
        headers=ADMIN,
    )
    assert r.status_code == 404


def test_pdf_and_legacy_word_files_are_refused(people_store):
    assert _upload("list.pdf", b"%PDF").status_code == 422
    assert _upload("list.doc", b"x").status_code == 422
    assert _upload("list.xlsx", b"x").status_code == 422


def test_an_import_needs_the_admin(people_store):
    _team("billing")
    r = client.post(
        "/api/teams/billing/members/import",
        files={"file": ("m.txt", b"Ana\n", "text/plain")},
        headers=REVIEWER,
    )
    assert r.status_code == 403


def test_the_parser_reads_each_format_and_refuses_the_rest():
    assert parse_members("m.csv", b"name,role\nAna,agent\n")[0]["role"] == "agent"
    assert parse_members("m.md", b"Ana\n")[0]["name"] == "Ana"
    with pytest.raises(Exception, match="needs a name column"):
        parse_members("m.csv", b"email\nana@example.com\n")
    with pytest.raises(Exception, match="not supported yet"):
        parse_members("m.pdf", b"%PDF")
    with pytest.raises(Exception, match="at most 500"):
        parse_members("m.txt", ("Ana\n" * 501).encode())
    with pytest.raises(Exception, match="larger than 2 MB"):
        parse_members("m.txt", b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(Exception, match="unsupported"):
        parse_members("m.xlsx", b"x")


def test_a_name_repeated_in_the_file_without_an_id_is_flagged(people_store):
    _team("billing")
    body = _upload("members.txt", b"Zed\nzed\n").json()
    assert body["rows"][1]["problems"] == ["appears twice in this file"]


def test_a_row_that_clashes_with_an_earlier_one_at_commit_is_refused(people_store):
    _team("billing")
    # The first row adds Ana by ID. The second names Ana with no ID, so it would match the first
    # when written. The plan cannot see that, so the commit refuses and nothing is added.
    text = b"Ana, , E-1, agent\nAna\n"
    assert _upload("members.txt", text).json()["can_commit"] is True
    refused = _upload("members.txt", text, dry_run=False)
    assert refused.status_code == 409
    assert client.get("/api/people").json() == []


def test_the_plan_names_each_kind_of_problem(people_store):
    from app.schemas import ImportRowPlan

    people_store.create_team("billing", [_field(**LEVEL)], "Admin")
    ana = people_store.add_person("Ana", None, "Admin", employee_id="E-1")
    people_store.add_membership(ana.id, "billing", Role.agent, "Admin")
    ben = people_store.add_person("Ben", None, "Admin", employee_id="E-2")
    people_store.set_active(ben.id, False, "Left", "Admin")

    def row(line: int) -> ImportRowPlan:
        return ImportRowPlan(line=line, name="x", action="", problems=[])

    members = [
        Member("Ana", None, "E-1", Role.agent, {"level": "junior"}),  # already in the team
        Member("Ben", None, "E-2", Role.agent, {"level": "junior"}),  # inactive
        Member("Cy", None, None, Role.agent, {}),  # missing a required field
    ]
    plan = people_store.plan_import("billing", [row(2), row(3), row(4)], members)
    assert plan[0].problems == ["Ana is already in billing"]
    assert plan[1].problems == ["Ben is inactive"]
    assert plan[2].problems == ["Level is required"]
    assert all(p.action == "error" for p in plan)


def test_a_failed_bulk_import_writes_nothing(people_store):
    people_store.create_team("billing", [], "Admin")
    with pytest.raises(PeopleError, match="more than one"):
        people_store.import_members(
            "billing",
            [Member("Zed", None, None, Role.agent, {}), Member("Zed", None, None, Role.agent, {})],
            "Admin",
        )
    assert people_store.list_people() == []
