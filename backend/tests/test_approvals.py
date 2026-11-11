"""Requests an agent makes that an admin must approve, and the admin's approve or reject."""

import pytest
from fastapi.testclient import TestClient

from app.approvals import ApprovalClosed, ApprovalNotFound, ApprovalStore, get_approval_store
from app.main import app
from app.schemas import Action, ApprovalStatus, Permission, Role
from app.store import MemoryTicketStore, SQLiteTicketStore, TicketNotFound
from tests.test_store import _record

client = TestClient(app)
ADMIN = {"X-User-Name": "Admin", "X-User-Role": "admin"}
AGENT = {"X-User-Name": "Sam", "X-User-Role": "agent"}
ANA = {"X-User-Name": "Ana", "X-User-Role": "agent"}
REVIEWER = {"X-User-Name": "Lee", "X-User-Role": "reviewer"}
VIEWER = {"X-User-Name": "Kim", "X-User-Role": "viewer"}
REFUND = {"subject": "Refund", "body": "I want my money back"}


def _pending(headers=AGENT) -> str:
    response = client.post("/api/triage", json=REFUND, headers=headers)
    assert response.status_code == 202
    return response.json()["id"]


def _ticket() -> str:
    return client.post("/api/triage", json=REFUND, headers=ADMIN).json()["ticket_id"]


# The approval store


def test_a_request_is_saved_pending_and_read_back(approval_store: ApprovalStore):
    made = approval_store.create(Permission.move, "t1", {"team": "billing"}, "Sam", Role.agent)
    assert made.status == ApprovalStatus.pending
    fetched = approval_store.get(made.id)
    assert fetched.payload == {"team": "billing"}
    assert fetched.requested_by == "Sam"
    assert fetched.requested_role == Role.agent
    assert fetched.decided_at is None


def test_an_unknown_request_raises(approval_store: ApprovalStore):
    with pytest.raises(ApprovalNotFound):
        approval_store.get("nope")


def test_listing_shows_everything_or_one_persons_requests(approval_store: ApprovalStore):
    approval_store.create(Permission.delete, "t1", {}, "Sam", Role.agent)
    approval_store.create(Permission.delete, "t2", {}, "Ana", Role.agent)
    assert len(approval_store.list()) == 2
    assert [r.requested_by for r in approval_store.list(requested_by="Sam")] == ["Sam"]


def test_a_request_can_be_decided_once(approval_store: ApprovalStore):
    made = approval_store.create(Permission.delete, "t1", {}, "Sam", Role.agent)
    decided = approval_store.decide(made.id, False, "Admin", "not needed")
    assert decided.status == ApprovalStatus.rejected
    assert decided.decided_by == "Admin"
    assert decided.decision_note == "not needed"
    assert decided.decided_at is not None
    with pytest.raises(ApprovalClosed):
        approval_store.decide(made.id, True, "Admin", "")


def test_an_approval_store_survives_a_restart(tmp_path):
    path = str(tmp_path / "nested" / "approvals.db")
    first = ApprovalStore(path)
    made = first.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    first.close()
    second = ApprovalStore(path)
    try:
        assert second.get(made.id).payload == {"tickets": []}
    finally:
        second.close()


# Gated actions wait for an admin


def test_an_agents_triage_waits_then_the_admin_approves_it(approval_store):
    pending = _pending()
    assert client.get("/api/tickets", headers=ADMIN).json() == []
    approved = client.post(f"/api/approvals/{pending}/approve", headers=ADMIN)
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decided_by"] == "Admin"
    assert len(client.get("/api/tickets", headers=ADMIN).json()) == 1


def test_a_reviewer_creates_directly_without_waiting(approval_store):
    assert client.post("/api/triage", json=REFUND, headers=REVIEWER).status_code == 200


def test_a_viewer_cannot_create(approval_store):
    assert client.post("/api/triage", json=REFUND, headers=VIEWER).status_code == 403


def test_an_agents_upload_waits_and_is_triaged_on_approval(approval_store):
    csv = b"subject,body\nRefund,money back\nHello,hi there\n"
    response = client.post(
        "/api/tickets/upload", files={"file": ("t.csv", csv, "text/csv")}, headers=AGENT
    )
    assert response.status_code == 202
    assert client.get("/api/tickets", headers=ADMIN).json() == []
    client.post(f"/api/approvals/{response.json()['id']}/approve", headers=ADMIN)
    assert len(client.get("/api/tickets", headers=ADMIN).json()) == 2


def test_a_viewer_cannot_upload(approval_store):
    response = client.post(
        "/api/tickets/upload",
        files={"file": ("t.csv", b"subject\nHi\n", "text/csv")},
        headers=VIEWER,
    )
    assert response.status_code == 403


def test_an_agent_override_waits_then_is_applied_on_approval(approval_store):
    ticket_id = _ticket()
    body = {"action": "escalate", "reason": "needs a person"}
    pending = client.post(f"/api/tickets/{ticket_id}/override", json=body, headers=AGENT)
    assert pending.status_code == 202
    assert client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).json()["override"] is None

    client.post(f"/api/approvals/{pending.json()['id']}/approve", headers=ADMIN)
    ticket = client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).json()
    assert ticket["override"]["action"] == "escalate"
    assert ticket["history"][-1]["actor"] == "Sam"


def test_an_agent_move_waits_then_moves_on_approval(approval_store):
    ticket_id = _ticket()
    pending = client.post(f"/api/tickets/{ticket_id}/team", json={"team": "billing"}, headers=AGENT)
    assert pending.status_code == 202
    assert pending.json()["ticket_id"] == ticket_id
    client.post(f"/api/approvals/{pending.json()['id']}/approve", headers=ADMIN)
    assert client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).json()["team"] == "billing"


def test_an_agent_delete_waits_then_removes_on_approval(approval_store):
    ticket_id = _ticket()
    pending = client.delete(f"/api/tickets/{ticket_id}", headers=AGENT)
    assert pending.status_code == 202
    assert client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).status_code == 200
    client.post(f"/api/approvals/{pending.json()['id']}/approve", headers=ADMIN)
    assert client.get(f"/api/tickets/{ticket_id}", headers=ADMIN).status_code == 404


def test_a_reviewer_moves_directly_and_an_admin_deletes_directly(approval_store):
    ticket_id = _ticket()
    moved = client.post(
        f"/api/tickets/{ticket_id}/team", json={"team": "billing"}, headers=REVIEWER
    )
    assert moved.status_code == 200
    assert client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN).status_code == 204
    assert client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN).status_code == 404


def test_a_viewer_cannot_delete_or_move(approval_store):
    ticket_id = _ticket()
    assert client.delete(f"/api/tickets/{ticket_id}", headers=VIEWER).status_code == 403
    moved = client.post(f"/api/tickets/{ticket_id}/team", json={"team": "x"}, headers=VIEWER)
    assert moved.status_code == 403


def test_a_gated_action_on_a_ticket_you_cannot_see_is_a_404(approval_store):
    ticket_id = _ticket()
    client.post(f"/api/tickets/{ticket_id}/team", json={"team": "billing"}, headers=ADMIN)
    outsider = {"X-User-Name": "Nobody", "X-User-Role": "agent"}
    assert client.delete(f"/api/tickets/{ticket_id}", headers=outsider).status_code == 404


# Deciding requests


def test_agents_see_only_their_own_requests_and_admins_see_all(approval_store):
    _pending(AGENT)
    _pending(ANA)
    assert {r["requested_by"] for r in client.get("/api/approvals", headers=AGENT).json()} == {
        "Sam"
    }
    assert len(client.get("/api/approvals", headers=ADMIN).json()) == 2


def test_only_an_admin_may_approve_or_reject(approval_store):
    pending = _pending()
    assert client.post(f"/api/approvals/{pending}/approve", headers=REVIEWER).status_code == 403
    rejected = client.post(
        f"/api/approvals/{pending}/reject", json={"note": "no"}, headers=REVIEWER
    )
    assert rejected.status_code == 403


def test_rejecting_needs_a_reason_and_changes_nothing(approval_store):
    pending = _pending()
    blank = client.post(f"/api/approvals/{pending}/reject", json={"note": "  "}, headers=ADMIN)
    assert blank.status_code == 422
    rejected = client.post(
        f"/api/approvals/{pending}/reject", json={"note": "Not this week"}, headers=ADMIN
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get("/api/tickets", headers=ADMIN).json() == []


def test_a_decided_request_cannot_be_decided_again(approval_store):
    pending = _pending()
    client.post(f"/api/approvals/{pending}/approve", headers=ADMIN)
    assert client.post(f"/api/approvals/{pending}/approve", headers=ADMIN).status_code == 409
    late = client.post(f"/api/approvals/{pending}/reject", json={"note": "late"}, headers=ADMIN)
    assert late.status_code == 409


def test_an_unknown_request_is_404(approval_store):
    assert client.post("/api/approvals/nope/approve", headers=ADMIN).status_code == 404
    rejected = client.post("/api/approvals/nope/reject", json={"note": "x"}, headers=ADMIN)
    assert rejected.status_code == 404


def test_an_approved_change_that_no_longer_applies_stays_pending(approval_store):
    ticket_id = _ticket()
    pending = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "check"},
        headers=AGENT,
    ).json()["id"]
    client.post(f"/api/tickets/{ticket_id}/resolve", headers=ADMIN)
    failed = client.post(f"/api/approvals/{pending}/approve", headers=ADMIN)
    assert failed.status_code == 409
    assert approval_store.get(pending).status == ApprovalStatus.pending


def test_an_approved_delete_of_a_missing_ticket_is_404(approval_store):
    pending = approval_store.create(Permission.delete, "gone", {}, "Sam", Role.agent)
    assert client.post(f"/api/approvals/{pending.id}/approve", headers=ADMIN).status_code == 404


def test_an_approved_change_with_no_ticket_is_refused(approval_store):
    pending = approval_store.create(Permission.move, None, {"team": "x"}, "Sam", Role.agent)
    assert client.post(f"/api/approvals/{pending.id}/approve", headers=ADMIN).status_code == 409


# Deleting tickets in the stores


@pytest.fixture(params=["memory", "sqlite"])
def ticket_store(request, tmp_path):
    if request.param == "memory":
        yield MemoryTicketStore()
    else:
        s = SQLiteTicketStore(str(tmp_path / "t.db"))
        yield s
        s.close()


def test_a_ticket_can_be_deleted_once(ticket_store):
    ticket_store.save(_record("t1", Action.escalate))
    ticket_store.delete("t1")
    with pytest.raises(TicketNotFound):
        ticket_store.get("t1")
    with pytest.raises(TicketNotFound):
        ticket_store.delete("t1")


def test_the_approval_store_opens_once_at_the_configured_path(tmp_path, monkeypatch):
    from app import approvals as approvals_module
    from app.config import get_settings

    monkeypatch.setattr(approvals_module, "_store", None)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "a.db"))
    get_settings.cache_clear()
    try:
        opened = get_approval_store()
        assert isinstance(opened, ApprovalStore)
        assert get_approval_store() is opened
        opened.close()
    finally:
        get_settings.cache_clear()
        monkeypatch.setattr(approvals_module, "_store", None)
