import pytest

from app.schemas import Action, Decision, TicketIn, TicketRecord, TicketStatus, TriageResult
from app.store import MemoryTicketStore, SQLiteTicketStore, TicketNotFound

TICKET = TicketIn(subject="Refund", body="I want my money back")


def _record(ticket_id: str, action: Action) -> TicketRecord:
    decision = Decision(
        action=action,
        reasoning="test",
        reply_text="Use Export." if action == Action.reply else None,
    )
    result = TriageResult(
        decision=decision, route="agent", provider="rules", failed_attempts=[], ticket_id=ticket_id
    )
    status = TicketStatus.replied if action == Action.reply else TicketStatus.escalated
    return TicketRecord(ticket_id=ticket_id, ticket=TICKET, result=result, status=status)


@pytest.fixture(params=["memory", "sqlite"])
def any_store(request, tmp_path):
    if request.param == "memory":
        yield MemoryTicketStore()
    else:
        s = SQLiteTicketStore(str(tmp_path / "tickets.db"))
        yield s
        s.close()


def test_save_then_get_round_trips(any_store):
    record = _record("t1", Action.escalate)
    assert any_store.save(record) == record
    assert any_store.get("t1") == record


def test_missing_ticket_raises(any_store):
    with pytest.raises(TicketNotFound):
        any_store.get("nope")


def test_queue_holds_only_escalations(any_store):
    any_store.save(_record("t1", Action.escalate))
    any_store.save(_record("t2", Action.reply))
    assert [r.ticket_id for r in any_store.escalations()] == ["t1"]


def test_saving_again_updates_in_place_and_keeps_order(any_store):
    any_store.save(_record("old", Action.escalate))
    any_store.save(_record("new", Action.escalate))
    resolved = any_store.get("old").model_copy(
        update={"owner": "Priya", "status": TicketStatus.resolved}
    )
    any_store.save(resolved)
    assert any_store.get("old").owner == "Priya"
    assert [r.ticket_id for r in any_store.list_all()] == ["new", "old"]
    assert [r.ticket_id for r in any_store.escalations()] == ["new"]


def test_list_all_is_newest_first(any_store):
    any_store.save(_record("old", Action.reply))
    any_store.save(_record("new", Action.escalate))
    assert [r.ticket_id for r in any_store.list_all()] == ["new", "old"]


def test_list_all_is_empty_to_start(any_store):
    assert any_store.list_all() == []


def test_sqlite_survives_a_restart(tmp_path):
    path = str(tmp_path / "tickets.db")
    first = SQLiteTicketStore(path)
    first.save(_record("t1", Action.escalate).model_copy(update={"owner": "Priya"}))
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


def test_sqlite_in_memory(tmp_path):
    s = SQLiteTicketStore(":memory:")
    try:
        assert s.list_all() == []
    finally:
        s.close()


def test_get_store_opens_sqlite_once(tmp_path, monkeypatch):
    from app import store as store_module

    monkeypatch.setattr(store_module, "_store", None)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "x.db"))
    store_module.get_settings.cache_clear()
    try:
        first = store_module.get_store()
        assert isinstance(first, SQLiteTicketStore)
        assert store_module.get_store() is first
        first.close()
    finally:
        store_module.get_settings.cache_clear()
