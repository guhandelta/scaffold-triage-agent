"""Archiving instead of deleting, restoring, what an archived ticket refuses, and the cleanup."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.approvals import ApprovalStore
from app.main import app
from app.schemas import Action, ApprovalStatus, Permission, Role, now
from app.store import TicketNotFound
from tests.test_store import _record

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


# The cleanup


def _archived_long_ago(store, days: int, ticket_id: str = "old") -> None:
    record = _record(ticket_id, Action.escalate)
    store.save(record.model_copy(update={"archived_at": now() - timedelta(days=days)}))


def test_the_cleanup_removes_archives_past_their_retention(approval_store, store):
    _archived_long_ago(store, 200, "old")
    _archived_long_ago(store, 10, "recent")
    result = client.post("/api/maintenance/sweep", headers=ADMIN).json()
    assert result["purged_tickets"] == 1
    assert store.get("recent").ticket_id == "recent"
    with pytest.raises(TicketNotFound):
        store.get("old")


def test_the_cleanup_is_admin_only(approval_store):
    assert client.post("/api/maintenance/sweep", headers=REVIEWER).status_code == 403


def test_a_request_for_an_archived_ticket_is_closed_by_the_cleanup(approval_store):
    ticket_id = _ticket()
    pending = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "x"},
        headers={"X-User-Name": "Sam", "X-User-Role": "agent"},
    ).json()["id"]
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)
    result = client.post("/api/maintenance/sweep", headers=ADMIN).json()
    assert result["expired_requests"] == 1
    closed = client.get(f"/api/approvals/{pending}", headers=ADMIN).json()
    assert closed["status"] == "expired"
    assert closed["decision_note"] == "the ticket was archived or removed"


def test_an_open_request_for_a_live_ticket_stays_pending(approval_store):
    ticket_id = _ticket()
    client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "x"},
        headers={"X-User-Name": "Sam", "X-User-Role": "agent"},
    )
    result = client.post("/api/maintenance/sweep", headers=ADMIN).json()
    assert result["expired_requests"] == 0
    assert approval_store.pending()


def test_a_request_nobody_decides_expires_after_its_window(approval_store):
    made = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    approval_store._db.execute(
        "UPDATE approvals SET created_at = ? WHERE id = ?",
        ((now() - timedelta(days=60)).isoformat(), made.id),
    )
    approval_store._db.commit()
    result = client.post("/api/maintenance/sweep", headers=ADMIN).json()
    assert result["expired_requests"] == 1
    closed = approval_store.get(made.id)
    assert closed.status == ApprovalStatus.expired
    assert closed.decided_by == "system"
    assert closed.decision_note == "no decision in 30 days"


def test_old_decided_requests_are_purged_but_pending_ones_are_not(approval_store: ApprovalStore):
    done = approval_store.create(Permission.create, None, {}, "Sam", Role.agent)
    approval_store.decide(done.id, False, "Admin", "no")
    waiting = approval_store.create(Permission.create, None, {}, "Sam", Role.agent)
    assert approval_store.purge_decided_before(now() + timedelta(days=1)) == 1
    assert approval_store.pending() == [approval_store.get(waiting.id)]


def test_expiring_a_request_is_kept_not_deleted(approval_store: ApprovalStore):
    made = approval_store.create(Permission.delete, "t1", {}, "Sam", Role.agent)
    expired = approval_store.expire(made.id, "gone")
    assert expired.status == ApprovalStatus.expired
    assert expired.decision_note == "gone"


def test_retention_must_be_at_least_one_day():
    from pydantic import ValidationError

    from app.org_config import OrgConfig

    with pytest.raises(ValidationError):
        OrgConfig.model_validate({"retention": {"archived_days": 0}})


def test_a_card_whose_ticket_was_removed_shows_no_ticket(approval_store, store):
    ticket_id = _ticket()
    pending = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "x"},
        headers={"X-User-Name": "Sam", "X-User-Role": "agent"},
    ).json()["id"]
    store.delete(ticket_id)
    detail = client.get(f"/api/approvals/{pending}", headers=ADMIN).json()
    assert detail["current"] is None


def test_a_young_batch_request_is_left_alone_by_the_cleanup(approval_store):
    batch = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    result = client.post("/api/maintenance/sweep", headers=ADMIN).json()
    assert result["expired_requests"] == 0
    assert approval_store.get(batch.id).status == ApprovalStatus.pending


def test_a_request_for_a_ticket_that_no_longer_exists_is_closed(approval_store):
    made = approval_store.create(Permission.delete, "removed-long-ago", {}, "Sam", Role.agent)
    result = client.post("/api/maintenance/sweep", headers=ADMIN).json()
    assert result["expired_requests"] == 1
    assert approval_store.get(made.id).decision_note == "the ticket was archived or removed"
