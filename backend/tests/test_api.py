from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_names_the_agent_and_counts_doc_sections():
    assert client.get("/api/health").json() == {
        "status": "ok",
        "organization": "Test Co",
        "agent": "rules",
        "docs": 4,
    }


def test_replies_from_the_docs_and_cites_the_section():
    r = client.post(
        "/api/triage",
        json={"subject": "Export data", "body": "How do I export my project data? It is large."},
    )
    assert r.status_code == 200
    decision = r.json()["decision"]
    assert decision["action"] == "reply"
    assert "choose Export" in decision["reply_text"]
    assert decision["citations"] == ["product/export#export-your-data-to-csv"]
    assert r.json()["sources"][0]["id"] == "product/export#export-your-data-to-csv"


def test_escalates_sensitive_tickets():
    r = client.post("/api/triage", json={"subject": "Refund", "body": "I want my money back"})
    assert r.json()["decision"]["action"] == "escalate"
    assert r.json()["decision"]["reply_text"] is None


def test_escalates_when_no_doc_covers_the_question():
    r = client.post("/api/triage", json={"subject": "Hi", "body": "What is the meaning of life?"})
    assert r.json()["decision"]["action"] == "escalate"
    assert r.json()["sources"] == []


def test_rejects_empty_body():
    assert client.post("/api/triage", json={"subject": "x", "body": ""}).status_code == 422
