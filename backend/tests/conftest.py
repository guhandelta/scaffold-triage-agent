"""Keep tests deterministic and offline.

- The triage chain uses offline rules, never a live model, even when .env has keys.
- Tickets go to a fresh in-memory store, never the real database.
- The agent reads a small fixed set of docs in tests/fixtures/docs, not the editable ones,
  with the config in tests/fixtures/triage.yaml.
Tests that want something else still override these dependencies.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.agent import get_chain
from app.agent.providers import FallbackChain, RulesProvider
from app.kb import KnowledgeBase, get_kb
from app.main import app
from app.org_config import OrgConfig, get_org_config, load
from app.people import PeopleStore, get_people_store
from app.store import MemoryTicketStore, get_store

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_DOCS = FIXTURES / "docs"


@pytest.fixture
def fixture_kb() -> KnowledgeBase:
    return KnowledgeBase.load(FIXTURE_DOCS)


@pytest.fixture
def org_config() -> OrgConfig:
    return load(FIXTURES / "triage.yaml")


@pytest.fixture
def store() -> MemoryTicketStore:
    return MemoryTicketStore()


@pytest.fixture
def people_store() -> Iterator[PeopleStore]:
    store = PeopleStore(":memory:")
    yield store
    store.close()


@pytest.fixture(autouse=True)
def offline_app(fixture_kb, store, org_config, people_store):
    app.dependency_overrides[get_people_store] = lambda: people_store
    app.dependency_overrides[get_chain] = lambda: FallbackChain([RulesProvider(org_config)])
    app.dependency_overrides[get_org_config] = lambda: org_config
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_kb] = lambda: fixture_kb
    yield
    app.dependency_overrides.clear()
