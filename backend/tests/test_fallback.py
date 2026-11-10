import asyncio

from app.agent.providers import FallbackChain, parse_decision
from app.schemas import Action, Decision, TicketIn

TICKET = TicketIn(subject="How do I export?", body="Where is export?")
REPLY = Decision(action=Action.reply, reasoning="docs", reply_text="Use Export.")


class Fake:
    def __init__(self, name, result=None, error=None):
        self.name, self._result, self._error, self.calls = name, result, error, 0

    async def decide(self, ticket, sources=()):
        self.calls += 1
        if self._error:
            raise self._error
        return self._result


def run(chain):
    return asyncio.run(chain.decide(TICKET))


def test_first_provider_answers_and_later_ones_are_not_called():
    a, b = Fake("a", REPLY), Fake("b", REPLY)
    decision, used, errors = run(FallbackChain([a, b]))
    assert used == "a" and errors == [] and decision.action == Action.reply
    assert b.calls == 0


def test_failure_moves_to_next_provider():
    a = Fake("a", error=RuntimeError("429 rate limited"))
    b = Fake("b", REPLY)
    decision, used, errors = run(FallbackChain([a, b]))
    assert used == "b" and decision.action == Action.reply
    assert "429" in errors[0]


def test_every_provider_failing_escalates():
    chain = FallbackChain([Fake("a", error=RuntimeError("down")), Fake("b", error=ValueError("x"))])
    decision, used, errors = run(chain)
    assert used == "none" and decision.action == Action.escalate
    assert len(errors) == 2


def test_parse_accepts_fenced_json_and_rejects_junk():
    text = 'Here you go:\n```json\n{"action": "reply", "reasoning": "ok", "reply_text": "Hi"}\n```'
    assert parse_decision(text).reply_text == "Hi"
    try:
        parse_decision("not json")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_reply_decision_must_carry_text():
    from pydantic import ValidationError

    from app.schemas import Decision

    try:
        Decision(action=Action.reply, reasoning="x", reply_text=None)
    except ValidationError:
        pass
    else:
        raise AssertionError("a reply with no text should be rejected")
    assert Decision(action=Action.escalate, reasoning="x").reply_text is None
