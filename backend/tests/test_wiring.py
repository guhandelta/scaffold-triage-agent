"""Startup wiring: which providers exist, in what order, and where tickets are kept."""

import asyncio
from types import SimpleNamespace as NS

import pytest

from app import store as store_module
from app.agent import get_chain
from app.agent.providers import (
    ClaudeProvider,
    FallbackChain,
    GoogleProvider,
    OpenAIProvider,
    RulesProvider,
    build_chain,
)
from app.config import Settings, get_settings
from app.schemas import TicketIn
from app.store import SQLiteTicketStore, get_store


def _settings(**overrides) -> Settings:
    base = dict(
        anthropic_api_key=None,
        openai_api_key=None,
        google_api_key=None,
        provider_order="claude,openai,google",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_no_keys_falls_back_to_rules():
    chain = build_chain(_settings())
    assert [type(p) for p in chain.providers] == [RulesProvider]


def test_providers_follow_provider_order_and_skip_missing_keys():
    chain = build_chain(
        _settings(
            anthropic_api_key="a",
            google_api_key="g",
            provider_order="google, bogus, claude, openai",
        )
    )
    assert [type(p) for p in chain.providers] == [GoogleProvider, ClaudeProvider]


def test_all_three_keys_build_three_providers():
    chain = build_chain(_settings(anthropic_api_key="a", openai_api_key="o", google_api_key="g"))
    assert [type(p) for p in chain.providers] == [ClaudeProvider, OpenAIProvider, GoogleProvider]


def test_provider_names_trim_and_drop_blanks():
    s = _settings(provider_order=" claude , , openai ")
    assert s.provider_names == ["claude", "openai"]


def test_cors_origins_split_and_trim():
    s = _settings(cors_origins=" http://a , http://b ,")
    assert s.cors_origin_list == ["http://a", "http://b"]


def test_get_chain_is_built_once_from_settings(monkeypatch):
    get_chain.cache_clear()
    monkeypatch.setattr(
        "app.agent.build_chain", lambda s: FallbackChain([RulesProvider()]), raising=True
    )
    first = get_chain()
    assert isinstance(first, FallbackChain)
    assert get_chain() is first
    get_chain.cache_clear()


def test_get_store_opens_sqlite_at_the_configured_path(tmp_path, monkeypatch):
    path = tmp_path / "x" / "tickets.db"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    get_settings.cache_clear()
    monkeypatch.setattr(store_module, "_store", None)
    try:
        opened = get_store()
        assert isinstance(opened, SQLiteTicketStore)
        assert path.exists()
        assert get_store() is opened
    finally:
        if store_module._store is not None:
            store_module._store.close()
        monkeypatch.setattr(store_module, "_store", None)
        get_settings.cache_clear()


def test_claude_refusal_is_a_failure():
    from app.agent.providers import ClaudeProvider as Claude

    p = Claude("k", "claude-opus-5-5")

    async def create(**kwargs):
        return NS(stop_reason="refusal", content=[])

    p.client = NS(messages=NS(create=create))
    with pytest.raises(RuntimeError, match="refused"):
        asyncio.run(p.decide(TicketIn(subject="s", body="b")))
