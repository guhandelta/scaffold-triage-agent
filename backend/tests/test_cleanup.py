"""The cleanup: the sweep only proposes, admins confirm or dismiss, and keep protects tickets."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.approvals import ApprovalClosed, ApprovalNotFound, NoticeNotFound
from app.main import app
from app.org_config import OrgConfig
from app.schemas import Action, ApprovalStatus, CleanupKind, NoticeStatus, Permission, Role, now
from app.store import TicketNotFound
from tests.test_store import _record

client = TestClient(app)
ADMIN = {"X-User-Name": "Admin", "X-User-Role": "admin"}
AGENT = {"X-User-Name": "Sam", "X-User-Role": "agent"}
REVIEWER = {"X-User-Name": "Lee", "X-User-Role": "reviewer"}
REFUND = {"subject": "Refund", "body": "I want my money back"}


def _ticket() -> str:
    return client.post("/api/triage", json=REFUND, headers=ADMIN).json()["ticket_id"]


def _archive_long_ago(store, ticket_id: str, days: int = 400) -> None:
    record = _record(ticket_id, Action.escalate)
    store.save(record.model_copy(update={"archived_at": now() - timedelta(days=days)}))


def _age_request(approvals, request_id: str, column: str, days: int) -> None:
    approvals._db.execute(
        f"UPDATE approvals SET {column} = ? WHERE id = ?",
        ((now() - timedelta(days=days)).isoformat(), request_id),
    )
    approvals._db.commit()


def _notices(headers=ADMIN) -> list[dict]:
    return client.get("/api/maintenance/notices", headers=headers).json()


def _sweep() -> dict:
    return client.post("/api/maintenance/sweep", headers=ADMIN).json()


# The sweep only proposes


def test_the_sweep_changes_nothing_it_only_raises_notices(approval_store, store):
    _archive_long_ago(store, "old")
    made = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    _age_request(approval_store, made.id, "created_at", 60)

    assert _sweep()["noticed"] == 2
    assert store.get("old").archived_at is not None
    assert approval_store.get(made.id).status == ApprovalStatus.pending


def test_a_pending_request_closes_only_after_the_admin_confirms(approval_store):
    ticket_id = _ticket()
    pending = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "x"},
        headers=AGENT,
    ).json()["id"]
    client.delete(f"/api/tickets/{ticket_id}", headers=ADMIN)

    _sweep()
    assert client.get(f"/api/approvals/{pending}", headers=ADMIN).json()["status"] == "pending"
    notice = _notices()[0]
    assert notice["kind"] == "expire_request"
    confirmed = client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN)
    assert confirmed.status_code == 200
    closed = client.get(f"/api/approvals/{pending}", headers=ADMIN).json()
    assert closed["status"] == "expired"
    assert closed["decided_by"] == "Admin"
    assert closed["decision_note"] == "Close as expired: its ticket was archived or removed"


def test_a_request_nobody_decides_is_proposed_after_its_window(approval_store):
    made = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    _age_request(approval_store, made.id, "created_at", 60)
    assert _sweep()["noticed"] == 1
    assert _notices()[0]["summary"] == "Close as expired: nobody decided it in 30 days"


def test_a_young_pending_request_raises_no_notice(approval_store):
    approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    assert _sweep()["noticed"] == 0


def test_an_old_decided_request_is_proposed_for_removal(approval_store):
    made = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    approval_store.decide(made.id, False, "Admin", "no")
    _age_request(approval_store, made.id, "decided_at", 400)
    assert _sweep()["noticed"] == 1
    notice = _notices()[0]
    assert notice["kind"] == "remove_request"
    client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN)
    with pytest.raises(ApprovalNotFound):
        approval_store.get(made.id)


def test_an_old_archive_is_proposed_and_removed_on_confirm(approval_store, store):
    _archive_long_ago(store, "old")
    assert _sweep()["noticed"] == 1
    notice = _notices()[0]
    assert notice["kind"] == "remove_ticket"
    assert notice["target_id"] == "old"
    assert (
        client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN).json()[
            "status"
        ]
        == "done"
    )
    with pytest.raises(TicketNotFound):
        store.get("old")


def test_a_recent_archive_is_not_proposed(approval_store, store):
    _archive_long_ago(store, "recent", days=30)
    assert _sweep()["noticed"] == 0


def test_a_kept_archive_is_never_proposed(approval_store, store):
    _archive_long_ago(store, "kept")
    store.save(store.get("kept").model_copy(update={"keep": True}))
    assert _sweep()["noticed"] == 0


def test_the_same_target_is_not_raised_twice(approval_store, store):
    _archive_long_ago(store, "old")
    assert _sweep()["noticed"] == 1
    assert _sweep()["noticed"] == 0
    assert len(_notices()) == 1


def test_a_dismissed_target_is_not_raised_again(approval_store, store):
    _archive_long_ago(store, "old")
    _sweep()
    dismissed = client.post(
        f"/api/maintenance/notices/{_notices()[0]['id']}/dismiss", headers=ADMIN
    )
    assert dismissed.json()["status"] == "dismissed"
    assert _sweep()["noticed"] == 0
    assert store.get("old").archived_at is not None


def test_a_ticket_kept_after_its_notice_is_not_removed(approval_store, store):
    _archive_long_ago(store, "old")
    _sweep()
    notice = _notices()[0]
    store.save(store.get("old").model_copy(update={"keep": True}))
    refused = client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN)
    assert refused.status_code == 409
    assert store.get("old").ticket_id == "old"


def test_a_ticket_restored_after_its_notice_is_not_removed(approval_store, store):
    _archive_long_ago(store, "old")
    _sweep()
    notice = _notices()[0]
    store.save(store.get("old").model_copy(update={"archived_at": None}))
    refused = client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN)
    assert refused.status_code == 409


def test_a_notice_for_a_ticket_already_removed_is_404(approval_store, store):
    _archive_long_ago(store, "old")
    _sweep()
    notice = _notices()[0]
    store.delete("old")
    assert (
        client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN).status_code
        == 404
    )


def test_a_request_notice_for_a_request_already_gone_is_404(approval_store):
    made = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    _age_request(approval_store, made.id, "created_at", 60)
    _sweep()
    notice = _notices()[0]
    approval_store.delete_request(made.id)
    assert (
        client.post(f"/api/maintenance/notices/{notice['id']}/confirm", headers=ADMIN).status_code
        == 404
    )


# Who may do what


def test_only_admins_sweep_see_and_decide_notices(approval_store, store):
    _archive_long_ago(store, "old")
    assert client.post("/api/maintenance/sweep", headers=REVIEWER).status_code == 403
    _sweep()
    notice_id = _notices()[0]["id"]
    assert client.get("/api/maintenance/notices", headers=REVIEWER).status_code == 403
    assert (
        client.post(f"/api/maintenance/notices/{notice_id}/confirm", headers=REVIEWER).status_code
        == 403
    )
    assert (
        client.post(f"/api/maintenance/notices/{notice_id}/dismiss", headers=REVIEWER).status_code
        == 403
    )


def test_an_unknown_or_decided_notice(approval_store, store):
    assert client.post("/api/maintenance/notices/nope/confirm", headers=ADMIN).status_code == 404
    assert client.post("/api/maintenance/notices/nope/dismiss", headers=ADMIN).status_code == 404
    _archive_long_ago(store, "old")
    _sweep()
    notice_id = _notices()[0]["id"]
    client.post(f"/api/maintenance/notices/{notice_id}/dismiss", headers=ADMIN)
    assert (
        client.post(f"/api/maintenance/notices/{notice_id}/confirm", headers=ADMIN).status_code
        == 409
    )
    assert (
        client.post(f"/api/maintenance/notices/{notice_id}/dismiss", headers=ADMIN).status_code
        == 409
    )


def test_the_store_reports_unknown_notices_and_closes_once(approval_store):
    with pytest.raises(NoticeNotFound):
        approval_store.get_notice("nope")
    notice = approval_store.add_notice(CleanupKind.remove_ticket, "t1", "Remove")
    approval_store.close_notice(notice.id, NoticeStatus.done, "Admin")
    with pytest.raises(ApprovalClosed):
        approval_store.close_notice(notice.id, NoticeStatus.dismissed, "Admin")


# Keep


def test_an_admin_marks_a_ticket_to_keep_and_can_unmark_it(approval_store):
    ticket_id = _ticket()
    kept = client.post(f"/api/tickets/{ticket_id}/keep", json={"keep": True}, headers=ADMIN)
    assert kept.json()["keep"] is True
    assert kept.json()["history"][-1]["kind"] == "kept"
    unkept = client.post(f"/api/tickets/{ticket_id}/keep", json={"keep": False}, headers=ADMIN)
    assert unkept.json()["history"][-1]["kind"] == "unkept"


def test_keeping_is_admin_only(approval_store):
    ticket_id = _ticket()
    assert (
        client.post(
            f"/api/tickets/{ticket_id}/keep", json={"keep": True}, headers=REVIEWER
        ).status_code
        == 403
    )


def test_a_card_whose_ticket_was_removed_shows_no_ticket(approval_store, store):
    ticket_id = _ticket()
    pending = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "x"},
        headers=AGENT,
    ).json()["id"]
    store.delete(ticket_id)
    assert client.get(f"/api/approvals/{pending}", headers=ADMIN).json()["current"] is None


def test_the_store_removes_old_requests_and_deletes_by_id(approval_store):
    made = approval_store.create(Permission.create, None, {"tickets": []}, "Sam", Role.agent)
    approval_store.decide(made.id, False, "Admin", "no")
    assert approval_store.decided_before(now() + timedelta(days=1))[0].id == made.id
    approval_store.delete_request(made.id)
    assert approval_store.decided_before(now() + timedelta(days=1)) == []


def test_retention_defaults_to_a_year():
    config = OrgConfig()
    assert config.retention.archived_days == 365
    assert config.retention.decided_requests_days == 365


def test_a_request_whose_ticket_was_removed_outright_is_proposed(approval_store, store):
    ticket_id = _ticket()
    pending = client.post(
        f"/api/tickets/{ticket_id}/override",
        json={"action": "escalate", "reason": "x"},
        headers=AGENT,
    ).json()["id"]
    store.delete(ticket_id)
    assert _sweep()["noticed"] == 1
    assert _notices()[0]["target_id"] == pending
