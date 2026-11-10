import pytest

from app.schemas import Action, Decision, TicketIn, TriageResult
from app.store import MemoryTicketStore, SQLiteTicketStore, TicketNotFound


def _result(ticket_id, action):
    return TriageResult(
        decision=Decision(
            action=action,
            reasoning="test",
            reply_text="Use Export." if action == Action.reply else None,
        ),
        route="agent",
        provider="rules",
        failed_attempts=[],
        ticket_id=ticket_id,
    )


TICKET = TicketIn(subject="Refund", body="I want my money back")


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    if request.param == "memory":
        yield MemoryTicketStore()
    else:
        s = SQLiteTicketStore(str(tmp_path / "tickets.db"))
        yield s
        s.close()


def test_save_then_get_round_trips(store):
    store.save(TICKET, _result("t1", Action.escalate))
    got = store.get("t1")
    assert got.ticket == TICKET
    assert got.result.decision.action == Action.escalate
    assert got.owner is None


def test_missing_ticket_raises(store):
    with pytest.raises(TicketNotFound):
        store.get("nope")
    with pytest.raises(TicketNotFound):
        store.assign("nope", "Priya")


def test_queue_holds_only_escalations(store):
    store.save(TICKET, _result("t1", Action.escalate))
    store.save(TICKET, _result("t2", Action.reply))
    assert [r.ticket_id for r in store.escalations()] == ["t1"]


def test_assign_persists_owner(store):
    store.save(TICKET, _result("t1", Action.escalate))
    store.assign("t1", "Priya")
    assert store.get("t1").owner == "Priya"
    assert store.escalations()[0].owner == "Priya"


def test_sqlite_survives_a_restart(tmp_path):
    path = str(tmp_path / "tickets.db")
    first = SQLiteTicketStore(path)
    first.save(TICKET, _result("t1", Action.escalate))
    first.assign("t1", "Priya")
    first.close()

    second = SQLiteTicketStore(path)
    try:
        assert second.get("t1").owner == "Priya"
        assert [r.ticket_id for r in second.escalations()] == ["t1"]
    finally:
        second.close()


def test_sqlite_creates_missing_folder(tmp_path):
    path = tmp_path / "nested" / "dir" / "tickets.db"
    s = SQLiteTicketStore(str(path))
    try:
        assert path.exists()
    finally:
        s.close()
