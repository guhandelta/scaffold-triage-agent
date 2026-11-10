from fastapi.testclient import TestClient

from app.agent import get_chain
from app.agent.providers import FallbackChain
from app.main import app
from app.schemas import Action, Decision


class FakeProvider:
    name = "fake"

    def __init__(self):
        self.calls = 0

    async def decide(self, ticket, sources=()):
        self.calls += 1
        cited = [s.id for s in sources[:1]]
        return Decision(
            action=Action.reply, reasoning="ok", reply_text="Use Export.", citations=cited
        )


def _client(chain):
    app.dependency_overrides[get_chain] = lambda: chain
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_reports_which_model_decided_and_failures_before_it():
    class Broken:
        name = "broken"

        async def decide(self, ticket, sources=()):
            raise RuntimeError("429 rate limited")

    chain = FallbackChain([Broken(), FakeProvider()])
    r = _client(chain).post("/api/triage", json={"subject": "Export", "body": "Where is export?"})
    body = r.json()
    assert body["provider"] == "fake"
    assert body["route"] == "agent"
    assert "429" in body["failed_attempts"][0]
    assert body["decision"]["action"] == "reply"


def test_risky_ticket_never_reaches_a_model():
    fake = FakeProvider()
    r = _client(FallbackChain([fake])).post(
        "/api/triage", json={"subject": "Refund", "body": "I was charged twice"}
    )
    body = r.json()
    assert body["route"] == "human"
    assert body["provider"] == "rules"
    assert body["decision"]["action"] == "escalate"
    assert fake.calls == 0
