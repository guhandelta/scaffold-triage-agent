"""Team-scoped tickets: routing picks the team, people only see their teams' tickets, and a
reviewer can move a ticket to another team."""

from fastapi.testclient import TestClient

from app.main import app
from app.people import PeopleStore
from app.routing import Route, route_ticket
from app.schemas import Role, TicketIn

client = TestClient(app)
ADMIN = {"X-User-Name": "Admin", "X-User-Role": "admin"}
LEE = {"X-User-Name": "Lee", "X-User-Role": "reviewer"}
ANA = {"X-User-Name": "Ana", "X-User-Role": "agent"}
BEN = {"X-User-Name": "Ben", "X-User-Role": "agent"}
NOBODY = {"X-User-Name": "Nobody", "X-User-Role": "viewer"}
VIC = {"X-User-Name": "Vic", "X-User-Role": "viewer"}


def _person(store: PeopleStore, name: str, team: str | None, role: Role = Role.agent) -> str:
    pid = store.add_person(name, None, "Admin").id
    if team:
        store.add_membership(pid, team, role, "Admin")
    return pid


def _triage(subject: str, body: str = "please help") -> str:
    return client.post("/api/triage", json={"subject": subject, "body": body}).json()["ticket_id"]


def _ids(headers: dict, path: str = "/api/tickets") -> set[str]:
    return {t["ticket_id"] for t in client.get(path, headers=headers).json()}


# Routing


def test_routing_picks_the_first_team_whose_phrase_matches():
    teams = {"billing": ["invoice"], "support": ["login"]}
    ticket = TicketIn(subject="Login fails", body="my invoice")
    assert route_ticket(ticket, [], teams).team == "billing"
    assert route_ticket(TicketIn(subject="Login fails", body="x"), [], teams).team == "support"
    assert route_ticket(TicketIn(subject="hi", body="x"), [], teams).team is None
    assert route_ticket(TicketIn(subject="hi", body="x"), []).team is None


def test_a_human_routed_ticket_still_keeps_its_team():
    ticket = TicketIn(subject="Refund", body="invoice")
    decision = route_ticket(ticket, ["refund"], {"billing": ["invoice"]})
    assert decision.route is Route.human
    assert decision.team == "billing"


def test_a_ticket_records_the_team_it_was_routed_to():
    ticket_id = _triage("Where is my invoice")
    assert client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).json()["team"] == "billing"
    assert client.get(f"/api/tickets/{_triage('Hello')}", headers=ADMIN).json()["team"] is None


# Who sees what


def test_people_see_their_teams_tickets_and_the_unteamed_ones(people_store):
    _person(people_store, "Ana", "billing")
    _person(people_store, "Ben", "support")
    billing = _triage("Where is my invoice")
    support = _triage("Cannot login")
    open_to_all = _triage("Hello")

    assert _ids(ANA) == {billing, open_to_all}
    assert _ids(BEN) == {support, open_to_all}
    assert _ids(ADMIN) == {billing, support, open_to_all}


def test_a_ticket_outside_your_team_looks_missing(people_store):
    _person(people_store, "Ben", "support")
    billing = _triage("Where is my invoice")
    assert client.get(f"/api/tickets/{billing}", headers=BEN).status_code == 404
    assert (
        client.post(f"/api/tickets/{billing}/notes", json={"text": "hi"}, headers=BEN).status_code
        == 404
    )


def test_someone_not_in_the_directory_sees_only_unteamed_tickets(people_store):
    billing = _triage("Where is my invoice")
    open_to_all = _triage("Hello")
    assert _ids(NOBODY) == {open_to_all}
    assert client.get(f"/api/tickets/{billing}", headers=NOBODY).status_code == 404


def test_deactivated_people_lose_their_teams(people_store):
    pid = _person(people_store, "Ana", "billing")
    billing = _triage("Where is my invoice")
    assert billing in _ids(ANA)
    people_store.set_active(pid, False, "Left", "Admin")
    assert billing not in _ids(ANA)


def test_escalations_respect_teams(people_store):
    _person(people_store, "Ben", "support")
    refund = _triage("Refund", "invoice for the refund")
    assert refund in _ids(ADMIN, "/api/escalations")
    assert refund not in _ids(BEN, "/api/escalations")


# Moving a ticket


def test_a_reviewer_moves_a_ticket_and_the_old_team_loses_it(people_store):
    _person(people_store, "Lee", "billing", Role.reviewer)
    _person(people_store, "Ana", "billing")
    _person(people_store, "Ben", "support")
    ticket = _triage("Where is my invoice")

    moved = client.post(f"/api/tickets/{ticket}/team", json={"team": "support"}, headers=LEE)
    assert moved.status_code == 200
    assert moved.json()["team"] == "support"
    assert moved.json()["history"][-1]["kind"] == "team"
    assert moved.json()["history"][-1]["detail"] == "Moved to team support"
    assert ticket not in _ids(ANA)
    assert ticket in _ids(BEN)


def test_moving_needs_the_assign_permission_and_visibility(people_store):
    _person(people_store, "Vic", "billing", Role.viewer)
    _person(people_store, "Ben", "support")
    ticket = _triage("Where is my invoice")
    # Vic can see the billing ticket but viewers may not assign, so the answer is a 403.
    denied = client.post(f"/api/tickets/{ticket}/team", json={"team": "support"}, headers=VIC)
    assert denied.status_code == 403
    # Ben cannot see the ticket, so he gets the same 404 as for a missing one.
    hidden = client.post(f"/api/tickets/{ticket}/team", json={"team": "support"}, headers=BEN)
    assert hidden.status_code == 404


def test_a_resolved_ticket_cannot_be_moved(people_store):
    _person(people_store, "Lee", "billing", Role.reviewer)
    ticket = _triage("Hello")
    client.post(f"/api/tickets/{ticket}/resolve", headers=ADMIN)
    r = client.post(f"/api/tickets/{ticket}/team", json={"team": "support"}, headers=ADMIN)
    assert r.status_code == 409


def test_a_bad_team_name_is_rejected():
    ticket = _triage("Hello")
    r = client.post(f"/api/tickets/{ticket}/team", json={"team": "has spaces"}, headers=ADMIN)
    assert r.status_code == 422
