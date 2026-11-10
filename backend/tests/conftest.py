"""Keep the API tests deterministic: the triage route uses offline rules, never a live model.

Without this, a machine with API keys in .env would send test tickets to real models, whose
answers vary from run to run. Tests that want a specific provider still override get_chain.
"""

import pytest

from app.agent import get_chain
from app.agent.providers import FallbackChain, RulesProvider
from app.main import app
from app.store import MemoryTicketStore, get_store


@pytest.fixture(autouse=True)
def offline_chain():
    """Offline rules and a fresh in-memory store, so tests never touch the real database."""
    app.dependency_overrides[get_chain] = lambda: FallbackChain([RulesProvider()])
    app.dependency_overrides[get_store] = lambda: MemoryTicketStore()
    yield
    app.dependency_overrides.clear()
