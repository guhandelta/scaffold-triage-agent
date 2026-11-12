"""Archiving instead of deleting, restoring, what an archived ticket refuses, and the cleanup."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN = {"X-User-Name": "Admin", "X-User-Role": "admin"}
REVIEWER = {"X-User-Name": "Lee", "X-User-Role": "reviewer"}
VIEWER = {"X-User-Name": "Kim", "X-User-Role": "viewer"}
REFUND = {"subject": "Refund", "body": "I want my money back"}


def _ticket() -> str:
    return client.post("/api/triage", json=REFUND, headers=ADMIN).json()["ticket_id"]


def _ids(headers=ADMIN, query="") -> set[str]:
    return {t["ticket_id"] for t in client.get(f"/api/tickets{query}", headers=headers).json()}


# Archive and restore


def test_archiving_hides_a_ticket_but_keeps_it(approval_store):
    ticket_id = _ticket()
    assert client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN).status_code == 204
    assert ticket_id not in _ids()
    kept = client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).json()
    assert kept["archived_by"] == "Admin"
    assert kept["history"][-1]["kind"] == "archived"


def test_admins_can_list_archived_tickets_on_request_only(approval_store):
    ticket_id = _ticket()
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    assert ticket_id in _ids(query="?include_archived=true")
    assert ticket_id not in _ids(headers=REVIEWER, query="?include_archived=true")


def test_archived_tickets_leave_the_escalations_too(approval_store):
    ticket_id = _ticket()
    assert ticket_id in {
        t["ticket_id"] for t in client.get("/api/escalations", headers=ADMIN).json()
    }
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    assert ticket_id not in {
        t["ticket_id"] for t in client.get("/api/escalations", headers=ADMIN).json()
    }
    included = client.get("/api/escalations?include_archived=true", headers=ADMIN).json()
    assert ticket_id in {t["ticket_id"] for t in included}


def test_restoring_brings_a_ticket_back(approval_store):
    ticket_id = _ticket()
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    restored = client.post(f"/api/tickets/{ticket_id}/restore", headers=ADMIN)
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    assert restored.json()["history"][-1]["kind"] == "restored"
    assert ticket_id in _ids()


def test_restoring_a_live_ticket_is_refused(approval_store):
    ticket_id = _ticket()
    assert client.post(f"/api/tickets/{ticket_id}/restore", headers=ADMIN).status_code == 409


def test_only_admins_archive_or_restore_directly(approval_store):
    ticket_id = _ticket()
    assert client.delete(f"/api/tickets/{ticket_id}", headers=VIEWER).status_code == 403
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    assert client.post(f"/api/tickets/{ticket_id}/restore", headers=REVIEWER).status_code == 403


def test_an_archived_ticket_refuses_changes(approval_store):
    ticket_id = _ticket()
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    assert (
        client.post(
            f"/api/tickets/{ticket_id}/team", json={"team": "billing"}, headers=ADMIN
        ).status_code
        == 409
    )
    override = {"action": "escalate", "reason": "x"}
    assert (
        client.post(f"/api/tickets/{ticket_id}/override", json=override, headers=ADMIN).status_code
        == 409
    )
    assert client.post(f"/api/tickets/{ticket_id}/resolve", headers=ADMIN).status_code == 409


def test_an_archived_ticket_is_still_refused_after_restore_then_allows_changes(approval_store):
    ticket_id = _ticket()
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    client.post(f"/api/tickets/{ticket_id}/restore", headers=ADMIN)
    moved = client.post(f"/api/tickets/{ticket_id}/team", json={"team": "billing"}, headers=ADMIN)
    assert moved.status_code == 200
