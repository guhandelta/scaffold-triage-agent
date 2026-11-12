"""People, teams and roles: the store, the API, who may change them, and what happens on leaving."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.people import PeopleError, PeopleStore, PersonNotFound, get_people_store
from app.schemas import Role

client = TestClient(app)
ADMIN = {"X-User-Name": "Admin", "X-User-Role": "admin"}
AGENT = {"X-User-Name": "Sam", "X-User-Role": "agent"}
REVIEWER = {"X-User-Name": "Lee", "X-User-Role": "reviewer"}
VIEWER = {"X-User-Name": "Kim", "X-User-Role": "viewer"}


def _add(people_store: PeopleStore, name: str = "Priya", email: str | None = None):
    return people_store.add_person(name, email, actor="Admin")


# The people_store


def test_a_person_round_trips_and_lists_by_name(people_store):
    later = _add(people_store, "Zed")
    earlier = _add(people_store, "Ana", "ana@example.com")
    assert people_store.get_person(earlier.id).email == "ana@example.com"
    assert people_store.get_person(earlier.id).active is True
    assert [p.name for p in people_store.list_people()] == ["Ana", "Zed"]
    assert later.memberships == []


def test_unknown_person_raises(people_store):
    with pytest.raises(PersonNotFound):
        people_store.get_person("nope")
    with pytest.raises(PersonNotFound):
        people_store.history("nope")


def test_a_person_can_be_in_several_teams_with_a_role_in_each(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.reviewer, "Admin")
    person = people_store.add_membership(person.id, "support", Role.agent, "Admin")
    assert [(m.team, m.role) for m in person.memberships] == [
        ("billing", Role.reviewer),
        ("support", Role.agent),
    ]


def test_joining_a_team_twice_is_refused(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.agent, "Admin")
    with pytest.raises(PeopleError, match="already in billing"):
        people_store.add_membership(person.id, "billing", Role.reviewer, "Admin")


def test_changing_a_role_needs_the_person_in_that_team(people_store):
    person = _add(people_store)
    with pytest.raises(PeopleError, match="is not in billing"):
        people_store.change_role(person.id, "billing", Role.agent, "promotion", "Admin")


def test_changing_to_the_same_role_is_refused(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.agent, "Admin")
    with pytest.raises(PeopleError, match="already agent"):
        people_store.change_role(person.id, "billing", Role.agent, "no change", "Admin")


def test_a_role_change_is_recorded_with_its_reason(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.agent, "Admin")
    updated = people_store.change_role(
        person.id, "billing", Role.reviewer, "Passed review", "Admin"
    )
    assert updated.memberships[0].role == Role.reviewer
    last = people_store.history(person.id)[-1]
    assert last.kind == "role changed"
    assert last.detail == "billing: agent to reviewer. Reason: Passed review"
    assert last.actor == "Admin"


def test_removing_from_a_team(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.agent, "Admin")
    assert people_store.remove_membership(person.id, "billing", "Admin").memberships == []
    with pytest.raises(PeopleError, match="is not in billing"):
        people_store.remove_membership(person.id, "billing", "Admin")


def test_deactivating_and_reactivating(people_store):
    person = _add(people_store)
    assert people_store.set_active(person.id, False, "Left the company", "Admin").active is False
    with pytest.raises(PeopleError, match="already inactive"):
        people_store.set_active(person.id, False, "again", "Admin")
    assert people_store.set_active(person.id, True, "Came back", "Admin").active is True
    with pytest.raises(PeopleError, match="already active"):
        people_store.set_active(person.id, True, "again", "Admin")
    assert [e.kind for e in people_store.history(person.id)] == [
        "added",
        "deactivated",
        "reactivated",
    ]


def test_history_keeps_every_change_in_order(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.agent, "Admin")
    people_store.remove_membership(person.id, "billing", "Lee")
    events = people_store.history(person.id)
    assert [(e.kind, e.detail, e.actor) for e in events] == [
        ("added", "Added Priya", "Admin"),
        ("joined", "Joined billing as agent", "Admin"),
        ("left", "Left billing", "Lee"),
    ]
    assert events[0].at.tzinfo is not None


def test_a_failed_change_leaves_nothing_behind(people_store):
    person = _add(people_store)
    people_store.add_membership(person.id, "billing", Role.agent, "Admin")
    with pytest.raises(PeopleError):
        people_store.add_membership(person.id, "billing", Role.reviewer, "Admin")
    assert len(people_store.history(person.id)) == 2


def test_the_store_survives_a_restart(tmp_path):
    path = str(tmp_path / "nested" / "people_store.db")
    first = PeopleStore(path)
    person = first.add_person("Priya", None, "Admin")
    first.add_membership(person.id, "billing", Role.agent, "Admin")
    first.close()

    second = PeopleStore(path)
    try:
        assert second.get_person(person.id).memberships[0].team == "billing"
    finally:
        second.close()


def test_get_people_opens_once_at_the_configured_path(tmp_path, monkeypatch):
    from app import people as people_module
    from app.config import get_settings

    monkeypatch.setattr(people_module, "_store", None)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "p.db"))
    get_settings.cache_clear()
    try:
        opened = get_people_store()
        assert isinstance(opened, PeopleStore)
        assert get_people_store() is opened
        opened.close()
    finally:
        get_settings.cache_clear()
        monkeypatch.setattr(people_module, "_store", None)


# The API: who may change people_store


def test_only_admins_may_change_people(people_store):
    for headers in (VIEWER, AGENT, REVIEWER):
        assert client.post("/api/people", json={"name": "New"}, headers=headers).status_code == 403
    admin = client.post("/api/people", json={"name": "New"}, headers=ADMIN)
    assert admin.status_code == 201


def test_anyone_may_read_the_directory(people_store):
    _add(people_store, "Priya")
    assert [p["name"] for p in client.get("/api/people", headers=VIEWER).json()] == ["Priya"]


def test_the_full_lifecycle_through_the_api(people_store):
    person = client.post(
        "/api/people", json={"name": "  Priya  ", "email": "priya@example.com"}, headers=ADMIN
    ).json()
    assert person["name"] == "Priya"
    assert person["memberships"] == []
    pid = person["id"]

    joined = client.post(
        f"/api/people/{pid}/memberships", json={"team": " Billing ", "role": "agent"}, headers=ADMIN
    ).json()
    assert joined["memberships"] == [{"team": "billing", "role": "agent", "details": {}}]

    promoted = client.patch(
        f"/api/people/{pid}/memberships/Billing",
        json={"role": "reviewer", "reason": "Passed the audit"},
        headers=ADMIN,
    ).json()
    assert promoted["memberships"][0]["role"] == "reviewer"

    left = client.delete(f"/api/people/{pid}/memberships/billing", headers=ADMIN).json()
    assert left["memberships"] == []

    kinds = [e["kind"] for e in client.get(f"/api/people/{pid}/history").json()]
    assert kinds == ["added", "joined", "role changed", "left"]
    assert client.get(f"/api/people/{pid}").json()["name"] == "Priya"


def test_unknown_people_are_404(people_store):
    missing = "/api/people/nope"
    assert client.get(missing).status_code == 404
    assert client.get(f"{missing}/history").status_code == 404
    assert (
        client.post(
            f"{missing}/memberships", json={"team": "a", "role": "agent"}, headers=ADMIN
        ).status_code
        == 404
    )
    assert client.delete(f"{missing}/memberships/a", headers=ADMIN).status_code == 404
    assert (
        client.post(
            f"{missing}/status", json={"active": False, "reason": "x"}, headers=ADMIN
        ).status_code
        == 404
    )


def test_conflicts_are_409_with_a_reason(people_store):
    pid = _add(people_store).id
    client.post(
        f"/api/people/{pid}/memberships", json={"team": "billing", "role": "agent"}, headers=ADMIN
    )
    again = client.post(
        f"/api/people/{pid}/memberships", json={"team": "billing", "role": "agent"}, headers=ADMIN
    )
    assert again.status_code == 409
    assert again.json()["detail"] == "Priya is already in billing"
    not_in = client.delete(f"/api/people/{pid}/memberships/support", headers=ADMIN)
    assert not_in.status_code == 409


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/people", {"name": "   "}),
        ("/api/people", {"name": "x", "email": "not-an-email"}),
        ("/api/people/x/memberships", {"team": "has spaces", "role": "agent"}),
        ("/api/people/x/memberships", {"team": "billing", "role": "ceo"}),
    ],
)
def test_bad_input_is_rejected(people_store, path, body):
    assert client.post(path, json=body, headers=ADMIN).status_code == 422


def test_a_role_change_needs_a_reason(people_store):
    pid = _add(people_store).id
    people_store.add_membership(pid, "billing", Role.agent, "Admin")
    r = client.patch(
        f"/api/people/{pid}/memberships/billing",
        json={"role": "reviewer", "reason": "  "},
        headers=ADMIN,
    )
    assert r.status_code == 422


# Leaving releases tickets


def test_deactivating_returns_open_tickets_to_the_queue(people_store):
    ticket = client.post(
        "/api/triage", json={"subject": "Refund", "body": "I want my money back"}
    ).json()
    done = client.post(
        "/api/triage", json={"subject": "Refund", "body": "refund for the second charge"}
    ).json()
    pid = _add(people_store, "Lee").id
    for tid in (ticket["ticket_id"], done["ticket_id"]):
        client.post(f"/api/tickets/{tid}/assign", json={"owner": "Lee"}, headers=ADMIN)
    client.post(f"/api/tickets/{done['ticket_id']}/resolve", headers=ADMIN)

    r = client.post(
        f"/api/people/{pid}/status", json={"active": False, "reason": "Left"}, headers=ADMIN
    )
    assert r.json()["active"] is False

    released = client.get(f"/api/tickets/{ticket['ticket_id']}", headers=ADMIN).json()
    assert released["owner"] is None
    assert released["history"][-1]["kind"] == "released"
    assert released["history"][-1]["actor"] == "Admin"
    # A resolved ticket keeps the owner it was closed with.
    assert client.get(f"/api/tickets/{done['ticket_id']}", headers=ADMIN).json()["owner"] == "Lee"


def test_reactivating_does_not_touch_tickets(people_store):
    pid = _add(people_store, "Lee").id
    client.post(
        f"/api/people/{pid}/status", json={"active": False, "reason": "Leave"}, headers=ADMIN
    )
    client.post("/api/triage", json={"subject": "Refund", "body": "I want my money back"}).json()
    back = client.post(
        f"/api/people/{pid}/status", json={"active": True, "reason": "Returned"}, headers=ADMIN
    )
    assert back.json()["active"] is True


def test_a_status_change_needs_a_reason_and_admin(people_store):
    pid = _add(people_store).id
    assert (
        client.post(
            f"/api/people/{pid}/status", json={"active": False, "reason": "x"}, headers=AGENT
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/people/{pid}/status", json={"active": False, "reason": " "}, headers=ADMIN
        ).status_code
        == 422
    )
