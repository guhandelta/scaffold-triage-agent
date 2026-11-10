"""The checks that keep replies tied to the docs, in the service and in the offline rules."""

import asyncio

from app.agent.providers import FallbackChain
from app.kb import get_kb
from app.schemas import Action, Decision, Source, TicketIn
from app.service import ground, run_triage
from app.store import MemoryTicketStore
from app.triage import decide


def _src(id_, *, human_only=False, policy=False, score=5.0):
    return Source(
        id=id_,
        area="a",
        title="T",
        heading="H",
        text="Do this.",
        human_only=human_only,
        policy=policy,
        score=score,
    )


DOC = _src("a/doc#x")
HUMAN = _src("a/doc#human", human_only=True)
POLICY = _src("policies/p#rule", policy=True)


def _reply(*citations):
    return Decision(action=Action.reply, reasoning="r", reply_text="hi", citations=list(citations))


def test_ground_keeps_a_cited_reply_and_drops_unknown_and_duplicate_citations():
    decision, note = ground(_reply("a/doc#x", "a/doc#x", "made/up#id"), [DOC])
    assert decision.action == Action.reply
    assert decision.citations == ["a/doc#x"]
    assert note == "Dropped 2 unknown citation(s)."


def test_ground_leaves_a_clean_reply_alone():
    assert ground(_reply("a/doc#x"), [DOC]) == (_reply("a/doc#x"), None)


def test_ground_escalates_a_reply_citing_a_human_only_section():
    decision, note = ground(_reply("a/doc#x", "a/doc#human"), [DOC, HUMAN])
    assert decision.action == Action.escalate
    assert decision.citations == ["a/doc#human"]
    assert "handled by a person" in note


def test_ground_escalates_a_reply_backed_only_by_policy_or_nothing():
    for cites in [("policies/p#rule",), ()]:
        decision, note = ground(_reply(*cites), [POLICY])
        assert decision.action == Action.escalate
        assert decision.reply_text is None
        assert "cited no support doc" in note


def test_ground_escalations_only_lose_unknown_citations():
    esc = Decision(action=Action.escalate, reasoning="r", citations=["a/doc#x", "zzz"])
    decision, note = ground(esc, [DOC])
    assert decision.citations == ["a/doc#x"]
    assert note == "Dropped 1 unknown citation(s)."
    assert ground(Decision(action=Action.escalate, reasoning="r"), [])[1] is None


class _Uncited:
    name = "fake"

    async def decide(self, ticket, sources=()):
        return Decision(action=Action.reply, reasoning="guess", reply_text="Try again later.")


def test_run_triage_logs_grounding_when_a_model_reply_is_unbacked(fixture_kb):
    store = MemoryTicketStore()
    ticket = TicketIn(subject="Export data", body="How do I export my project data?")
    record = asyncio.run(run_triage(ticket, FallbackChain([_Uncited()]), store, fixture_kb))
    assert record.decision.action == Action.escalate
    assert record.status == "escalated"
    assert [e.kind for e in record.history][-2:] == ["grounding", "decided"]
    assert store.get(record.ticket_id) == record


TICKET = TicketIn(subject="Question", body="something")


def test_rules_escalate_when_the_best_section_is_human_only():
    decision = decide(TICKET, [POLICY, HUMAN, DOC])
    assert decision.action == Action.escalate
    assert decision.citations == ["a/doc#human"]


def test_rules_escalate_a_weak_match():
    decision = decide(TICKET, [_src("a/doc#x", score=1.0)])
    assert decision.action == Action.escalate
    assert "weak match" in decision.reasoning
    assert decision.citations == []


def test_rules_reply_with_the_best_section():
    decision = decide(TICKET, [DOC])
    assert decision.action == Action.reply
    assert "Do this." in decision.reply_text
    assert decision.citations == ["a/doc#x"]


def test_get_kb_loads_the_configured_docs_once():
    get_kb.cache_clear()
    try:
        assert get_kb() is get_kb()
        assert len(get_kb().sections) >= 20
    finally:
        get_kb.cache_clear()
