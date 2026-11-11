"""Ticket detail, history, and the reviewer actions, with role-based permissions."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REFUND = {"subject": "Refund", "body": "I want my money back"}
EXPORT = {"subject": "Export data", "body": "How do I export my project data? It is large."}


def _triage(ticket):
    r = client.post("/api/triage", json=ticket)
    assert r.status_code == 200
    return r.json()["ticket_id"]


def _as(role, name="Priya"):
    return {"X-User-Role": role, "X-User-Name": name}


def test_me_defaults_to_the_configured_reviewer():
    me = client.get("/api/me").json()
    assert me == {
        "name": "Reviewer",
        "role": "reviewer",
        "permissions": ["assign", "confirm", "create", "move", "note", "override", "resolve"],
    }


def test_me_reads_the_headers():
    me = client.get("/api/me", headers=_as("  Agent ", "  Sam  ")).json()
    assert me == {
        "name": "Sam",
        "role": "agent",
        "permissions": ["assign", "create", "delete", "move", "note", "override"],
    }


def test_unknown_role_is_rejected():
    assert client.get("/api/me", headers={"X-User-Role": "ceo"}).status_code == 400


def test_detail_has_decision_sources_and_history():
    ticket_id = _triage(EXPORT)
    record = client.get(f"/api/tickets/{ticket_id}").json()
    assert record["status"] == "replied"
    assert record["decision"]["action"] == "reply"
    assert record["result"]["sources"][0]["id"] == "product/export#export-your-data-to-csv"
    kinds = [e["kind"] for e in record["history"]]
    assert kinds == ["received", "routed", "retrieved", "decided"]
    assert record["history"][-1]["actor"] == "rules"


def test_rule_escalated_ticket_joins_the_queue():
    ticket_id = _triage(REFUND)
    _triage(EXPORT)
    queue = client.get("/api/escalations").json()
    assert [item["ticket_id"] for item in queue] == [ticket_id]
    assert queue[0]["owner"] is None


def test_ticket_list_is_newest_first_and_includes_replies():
    first = _triage(EXPORT)
    second = _triage(REFUND)
    items = client.get("/api/tickets").json()
    assert [i["ticket_id"] for i in items] == [second, first]
    assert [i["decision"]["action"] for i in items] == ["escalate", "reply"]


def test_unknown_ticket_is_404():
    assert client.get("/api/tickets/nope").status_code == 404
    assert client.post("/api/tickets/nope/resolve").status_code == 404


def test_assign_sets_owner_trims_name_and_logs_who_did_it():
    ticket_id = _triage(REFUND)
    r = client.post(
        f"/api/tickets/{ticket_id}/assign", json={"owner": "  Lee  "}, headers=_as("agent")
    )
    assert r.status_code == 200
    assert r.json()["owner"] == "Lee"
    event = r.json()["history"][-1]
    assert (event["kind"], event["detail"], event["actor"]) == (
        "assigned",
        "Assigned to Lee",
        "Priya",
    )
    assert client.get("/api/escalations").json()[0]["owner"] == "Lee"


@pytest.mark.parametrize("owner", ["", "   "])
def test_blank_owner_is_rejected(owner):
    ticket_id = _triage(REFUND)
    assert client.post(f"/api/tickets/{ticket_id}/assign", json={"owner": owner}).status_code == 422


def test_note_is_kept_with_its_author():
    ticket_id = _triage(REFUND)
    r = client.post(f"/api/tickets/{ticket_id}/notes", json={"text": " Called them. "})
    assert r.status_code == 200
    assert r.json()["notes"][0]["author"] == "Reviewer"
    assert r.json()["notes"][0]["text"] == "Called them."
    assert r.json()["history"][-1]["kind"] == "note"


def test_confirm_records_the_reviewer():
    ticket_id = _triage(REFUND)
    r = client.post(f"/api/tickets/{ticket_id}/confirm", headers=_as("reviewer"))
    assert r.json()["confirmed_by"] == "Priya"
    assert r.json()["history"][-1]["detail"] == "Confirmed the decision to escalate"


def test_override_to_reply_takes_the_ticket_out_of_the_queue():
    ticket_id = _triage(REFUND)
    client.post(f"/api/tickets/{ticket_id}/confirm")
    r = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "reply", "reason": "Within 14 days", "reply_text": " Refund sent. "},
    )
    body = r.json()
    assert r.status_code == 200
    assert body["status"] == "replied"
    assert body["confirmed_by"] is None
    assert body["decision"]["reply_text"] == "Refund sent."
    assert body["decision"]["reasoning"] == "Overridden by Reviewer: Within 14 days"
    assert body["result"]["decision"]["action"] == "escalate"  # the agent's call is kept
    assert client.get("/api/escalations").json() == []


def test_override_to_escalate_puts_a_reply_in_the_queue():
    ticket_id = _triage(EXPORT)
    r = client.post(
        f"/api/tickets/{ticket_id}/override", json={"action": "escalate", "reason": "VIP customer"}
    )
    assert r.json()["status"] == "escalated"
    assert r.json()["decision"]["reply_text"] is None
    assert [i["ticket_id"] for i in client.get("/api/escalations").json()] == [ticket_id]


@pytest.mark.parametrize("reply_text", [None, "   "])
def test_reply_override_needs_text(reply_text):
    ticket_id = _triage(REFUND)
    r = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "reply", "reason": "ok", "reply_text": reply_text},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "a reply override needs reply_text"


def test_resolve_closes_the_ticket_and_blocks_further_changes():
    ticket_id = _triage(REFUND)
    r = client.post(f"/api/tickets/{ticket_id}/resolve")
    assert r.json()["status"] == "resolved"
    assert client.get("/api/escalations").json() == []
    for action in ("resolve", "confirm"):
        again = client.post(f"/api/tickets/{ticket_id}/{action}")
        assert again.status_code == 409
        assert again.json()["detail"] == "ticket is already resolved"
    override = client.post(
        f"/api/tickets/{ticket_id}/override", json={"action": "escalate", "reason": "x"}
    )
    assert override.status_code == 409
    # Notes and owners can still be added to a closed ticket.
    assert client.post(f"/api/tickets/{ticket_id}/notes", json={"text": "fyi"}).status_code == 200


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("viewer", set()),
        ("agent", {"assign", "notes"}),
        ("reviewer", {"assign", "notes", "confirm", "override", "resolve"}),
        ("admin", {"assign", "notes", "confirm", "override", "resolve"}),
    ],
)
def test_roles_decide_who_may_act(role, allowed):
    bodies = {
        "assign": {"owner": "Lee"},
        "notes": {"text": "hi"},
        "confirm": None,
        "override": {"action": "escalate", "reason": "check"},
        "resolve": None,
    }
    for action, body in bodies.items():
        ticket_id = _triage(REFUND)
        r = client.post(f"/api/tickets/{ticket_id}/{action}", json=body, headers=_as(role))
        if role == "agent" and action == "override":
            # Agents may ask for an override, but it waits for an admin.
            assert r.status_code == 202, (role, action)
        elif action in allowed:
            assert r.status_code == 200, (role, action)
        else:
            assert r.status_code == 403, (role, action)
            assert r.json()["detail"].startswith(f"{role} cannot")
