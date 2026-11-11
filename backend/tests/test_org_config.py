"""The per-organization config file, and how each part of the app follows it."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.providers import (
    ClaudeProvider,
    GoogleProvider,
    OpenAIProvider,
    RulesProvider,
    build_chain,
    system_prompt,
)
from app.config import Settings, get_settings
from app.kb import get_kb
from app.main import app
from app.org_config import (
    DEFAULT_CONFIG,
    DEFAULT_HUMAN_ONLY,
    ConfigError,
    OrgConfig,
    get_org_config,
    load,
    main,
)
from app.routing import Route, route_ticket
from app.schemas import Action, Permission, Role, Source, TicketIn
from app.triage import decide

client = TestClient(app)


def _write(tmp_path: Path, text: str, name: str = "triage.yaml") -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def _settings(**overrides) -> Settings:
    base = dict(anthropic_api_key=None, openai_api_key=None, google_api_key=None)
    return Settings(_env_file=None, **{**base, **overrides})


# Loading and checking the file


def test_the_shipped_config_loads():
    config = load(DEFAULT_CONFIG)
    assert config.organization.name == "Example Co"
    assert config.docs_dir == DEFAULT_CONFIG.parent / "data" / "docs"
    assert config.agent.providers == ["claude", "openai", "google"]
    assert config.access.permissions(Role.agent) == [
        Permission.assign,
        Permission.create,
        Permission.delete,
        Permission.move,
        Permission.note,
        Permission.override,
    ]


def test_an_empty_file_uses_safe_defaults(tmp_path):
    config = load(_write(tmp_path, ""))
    assert config.organization.name == "Your company"
    assert config.routing.human_only == list(DEFAULT_HUMAN_ONLY)
    assert config.docs_dir == tmp_path / "data" / "docs"
    assert config.access.default_role == Role.reviewer


def test_docs_path_can_be_absolute_and_phrases_are_normalized(tmp_path):
    docs = tmp_path / "elsewhere"
    config = load(
        _write(tmp_path, f"docs: {{path: {docs}}}\nrouting: {{human_only: ['  Refund NOW ']}}")
    )
    assert config.docs_dir == docs
    assert config.routing.human_only == ["refund now"]


def test_a_role_left_out_can_only_view(tmp_path):
    config = load(_write(tmp_path, "access:\n  roles:\n    admin: [resolve, resolve]\n"))
    assert config.access.permissions(Role.admin) == [Permission.resolve]
    assert config.access.permissions(Role.reviewer) == []


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("organisation: {name: x}", "organisation: Extra inputs are not permitted"),
        ("agent: {providers: [claude, mistral]}", "agent.providers.1"),
        ("access: {roles: {agent: [fly]}}", "access.roles.agent.0"),
        ("docs: {top_k: 0}", "docs.top_k"),
        ("organization: {name: '  '}", "organization.name"),
        ("- just\n- a list", "must be a mapping"),
        ("key: [unclosed", "not valid YAML"),
    ],
)
def test_mistakes_are_reported_clearly(tmp_path, text, message):
    with pytest.raises(ConfigError, match=message.replace(".", r"\.")):
        load(_write(tmp_path, text))


def test_a_missing_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load(tmp_path / "nope.yaml")


def test_get_org_config_reads_triage_config_once(tmp_path, monkeypatch):
    path = _write(tmp_path, "organization: {name: Acme}")
    monkeypatch.setenv("TRIAGE_CONFIG", str(path))
    get_settings.cache_clear()
    get_org_config.cache_clear()
    try:
        assert get_org_config().organization.name == "Acme"
        assert get_org_config() is get_org_config()
    finally:
        get_settings.cache_clear()
        get_org_config.cache_clear()


def test_get_kb_reads_the_docs_named_in_the_config(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "faq.md").write_text("## Opening hours\nNine to five.\n")
    monkeypatch.setenv("TRIAGE_CONFIG", str(_write(tmp_path, "docs: {path: docs}")))
    monkeypatch.delenv("DOCS_PATH", raising=False)
    for cached in (get_settings, get_org_config, get_kb):
        cached.cache_clear()
    try:
        assert [s.id for s in get_kb().sections] == ["faq#opening-hours"]
    finally:
        for cached in (get_settings, get_org_config, get_kb):
            cached.cache_clear()


# The check command


def test_check_command_summarizes_a_good_file(capsys):
    assert main([str(DEFAULT_CONFIG)]) == 0
    out = capsys.readouterr().out
    assert "OK: Example Co" in out
    assert "12 Markdown file(s)" in out
    assert "viewer:    view only" in out


def test_check_command_defaults_to_the_configured_file(capsys, monkeypatch):
    monkeypatch.delenv("TRIAGE_CONFIG", raising=False)
    get_settings.cache_clear()
    try:
        assert main([]) == 0
    finally:
        get_settings.cache_clear()
    assert "Example Co" in capsys.readouterr().out


def test_check_command_fails_on_errors_and_missing_docs(tmp_path, capsys):
    assert main([str(_write(tmp_path, "bogus: 1"))]) == 1
    assert "Config error" in capsys.readouterr().err
    assert main([str(_write(tmp_path, "agent: {providers: []}", "b.yaml"))]) == 1
    captured = capsys.readouterr()
    assert "offline rules only" in captured.out
    assert "does not exist" in captured.err


# The agent follows the config


def test_prompt_names_the_organization_and_adds_its_guidance():
    plain = OrgConfig()
    assert system_prompt(plain).startswith("You work for Your company.")
    custom = OrgConfig.model_validate(
        {
            "organization": {"name": "Acme", "product": "Rockets"},
            "agent": {"instructions": "  Be brief.  "},
        }
    )
    prompt = system_prompt(custom)
    assert prompt.startswith("You work for Acme, which makes Rockets.")
    assert prompt.endswith("never overrides the rules above):\nBe brief.")
    assert system_prompt() == system_prompt(None)
    assert "You work for" not in system_prompt()


def test_chain_uses_the_configured_order_and_models():
    config = OrgConfig.model_validate(
        {"agent": {"providers": ["google", "claude"], "models": {"google": "g-1", "claude": "c-1"}}}
    )
    keys = dict(anthropic_api_key="a", openai_api_key="o", google_api_key="g")
    chain = build_chain(_settings(**keys), config)
    assert [type(p) for p in chain.providers] == [GoogleProvider, ClaudeProvider]
    assert [p.model for p in chain.providers] == ["g-1", "c-1"]
    assert all(p.prompt == system_prompt(config) for p in chain.providers)


def test_env_overrides_win_over_the_config():
    settings = _settings(
        openai_api_key="o", provider_order="openai", openai_model="o-env", claude_model="c-env"
    )
    chain = build_chain(settings, OrgConfig())
    assert [type(p) for p in chain.providers] == [OpenAIProvider]
    assert chain.providers[0].model == "o-env"


def test_no_keys_gives_rules_that_follow_the_config():
    config = OrgConfig.model_validate({"routing": {"human_only": ["pineapple"]}})
    chain = build_chain(_settings(), config)
    assert isinstance(chain.providers[0], RulesProvider)
    decision = asyncio.run(chain.providers[0].decide(TicketIn(subject="Pineapple", body="x")))
    assert decision.reasoning == "Mentions 'pineapple', which needs a person."


DOC = Source(
    id="a/doc#x", area="a", title="T", heading="H", text="Do this.",
    human_only=False, policy=False, score=3.0,
)  # fmt: skip


def test_rules_reply_with_the_configured_wording_and_threshold():
    config = OrgConfig.model_validate(
        {"replies": {"greeting": "Hello there!", "closing": ""}, "agent": {"min_score": 1}}
    )
    decision = decide(TicketIn(subject="q", body="q"), [DOC], config)
    assert decision.reply_text == "Hello there!\n\nDo this."
    strict = OrgConfig.model_validate({"agent": {"min_score": 5}})
    assert decide(TicketIn(subject="q", body="q"), [DOC], strict).action == Action.escalate


def test_routing_uses_only_the_phrases_it_is_given():
    ticket = TicketIn(subject="Refund", body="please")
    assert route_ticket(ticket, ["refund"]).route is Route.human
    assert route_ticket(ticket, []).route is Route.agent


# The API follows the config


def _with_config(text: str, tmp_path: Path) -> OrgConfig:
    config = load(_write(tmp_path, text))
    app.dependency_overrides[get_org_config] = lambda: config
    return config


def test_roles_and_default_user_come_from_the_config(tmp_path):
    _with_config(
        "access:\n  default_user: Desk\n  default_role: agent\n"
        "  roles: {agent: [note, create]}\n  approval: {}\n",
        tmp_path,
    )
    assert client.get("/api/me").json() == {
        "name": "Desk",
        "role": "agent",
        "permissions": ["create", "note"],
    }
    ticket_id = client.post("/api/triage", json={"subject": "Hi", "body": "hello"}).json()[
        "ticket_id"
    ]
    assert client.post(f"/api/tickets/{ticket_id}/assign", json={"owner": "x"}).status_code == 403
    assert client.post(f"/api/tickets/{ticket_id}/notes", json={"text": "x"}).status_code == 200


def test_routing_and_top_k_come_from_the_config(tmp_path):
    _with_config("routing: {human_only: [export]}\ndocs: {top_k: 1}", tmp_path)
    body = client.post(
        "/api/triage", json={"subject": "Export data", "body": "How do I import a CSV?"}
    ).json()
    assert body["route"] == "human"
    assert len(body["sources"]) == 1
    assert client.get("/api/health").json()["organization"] == "Your company"


def test_the_example_organization_loads_and_answers_from_its_own_docs():
    from app.kb import KnowledgeBase

    config = load(Path(__file__).parents[2] / "examples" / "acme-hosting" / "triage.yaml")
    assert config.organization.name == "Acme Hosting"
    kb = KnowledgeBase.load(config.docs_dir)
    sources = kb.search("How do I turn on SSL for my domain?", k=config.docs.top_k)
    decision = decide(TicketIn(subject="SSL", body="turn on ssl"), sources, config)
    assert decision.action == Action.reply
    assert decision.reply_text.startswith("Hello,\n\n")
    assert decision.reply_text.endswith("Kind regards,\nAcme Hosting Support")
