"""Keep tests deterministic and offline.

- The triage chain uses offline rules, never a live model, even when .env has keys.
- Tickets go to a fresh in-memory store, never the real database.
- The agent reads a small fixed set of docs in tests/fixtures/docs, not the editable ones.
Tests that want something else still override these dependencies.
"""

from pathlib import Path

import pytest

from app.agent import get_chain
from app.agent.providers import FallbackChain, RulesProvider
from app.kb import KnowledgeBase, get_kb
from app.main import app
from app.store import MemoryTicketStore, get_store

FIXTURE_DOCS = Path(__file__).parent / "fixtures" / "docs"


@pytest.fixture
def fixture_kb() -> KnowledgeBase:
    return KnowledgeBase.load(FIXTURE_DOCS)


@pytest.fixture
def store() -> MemoryTicketStore:
    return MemoryTicketStore()


@pytest.fixture(autouse=True)
def offline_app(fixture_kb, store):
    app.dependency_overrides[get_chain] = lambda: FallbackChain([RulesProvider()])
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_kb] = lambda: fixture_kb
    yield
    app.dependency_overrides.clear()
