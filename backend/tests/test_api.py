from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok", "agent": "rules"}


def test_replies_to_a_plain_question():
    r = client.post("/api/triage", json={"subject": "Hi", "body": "How do I export?"})
    assert r.status_code == 200
    assert r.json()["action"] == "reply"
    assert r.json()["reply_text"]


def test_escalates_sensitive_tickets():
    r = client.post("/api/triage", json={"subject": "Refund", "body": "I want my money back"})
    assert r.json()["action"] == "escalate"
    assert r.json()["reply_text"] is None


def test_rejects_empty_body():
    assert client.post("/api/triage", json={"subject": "x", "body": ""}).status_code == 422
