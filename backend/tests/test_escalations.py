import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Action, Decision, TicketIn, TriageResult
from app.store import TicketStore, get_store


@pytest.fixture
def client():
    store = TicketStore()
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _triage(client, subject, body):
    r = client.post("/api/triage", json={"subject": subject, "body": body})
    assert r.status_code == 200
    return r.json()


def test_rule_escalated_ticket_joins_the_queue(client):
    t = _triage(client, "Refund", "I want my money back")
    queue = client.get("/api/escalations").json()
    assert [item["ticket_id"] for item in queue] == [t["ticket_id"]]
    assert queue[0]["owner"] is None


def test_replied_ticket_stays_out_of_the_queue(client):
    _triage(client, "How do I export?", "Where is the export button?")
    assert client.get("/api/escalations").json() == []


def test_assign_sets_owner_and_trims_name(client):
    t = _triage(client, "Refund", "I want my money back")
    r = client.post(f"/api/tickets/{t['ticket_id']}/assign", json={"owner": "  Priya  "})
    assert r.status_code == 200
    assert r.json()["owner"] == "Priya"
    assert client.get(f"/api/tickets/{t['ticket_id']}").json()["owner"] == "Priya"
    assert client.get("/api/escalations").json()[0]["owner"] == "Priya"


def test_assign_unknown_ticket_is_404(client):
    r = client.post("/api/tickets/nope/assign", json={"owner": "Priya"})
    assert r.status_code == 404


def test_get_unknown_ticket_is_404(client):
    assert client.get("/api/tickets/nope").status_code == 404


@pytest.mark.parametrize("owner", ["", "   "])
def test_blank_owner_is_rejected(client, owner):
    t = _triage(client, "Refund", "I want my money back")
    r = client.post(f"/api/tickets/{t['ticket_id']}/assign", json={"owner": owner})
    assert r.status_code == 422


def test_store_keeps_model_escalations_too():
    store = TicketStore()
    result = TriageResult(
        decision=Decision(action=Action.escalate, reasoning="unsure", reply_text=None),
        route="agent",
        provider="claude",
        failed_attempts=[],
        ticket_id="t1",
    )
    store.save(TicketIn(subject="s", body="b"), result)
    assert [r.ticket_id for r in store.escalations()] == ["t1"]
