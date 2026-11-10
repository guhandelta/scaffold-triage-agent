"""Keep the API tests deterministic: the triage route uses offline rules, never a live model.

Without this, a machine with API keys in .env would send test tickets to real models, whose
answers vary from run to run. Tests that want a specific provider still override get_chain.
"""

import pytest

from app.agent import get_chain
from app.agent.providers import FallbackChain, RulesProvider
from app.main import app


@pytest.fixture(autouse=True)
def offline_chain():
    app.dependency_overrides[get_chain] = lambda: FallbackChain([RulesProvider()])
    yield
    app.dependency_overrides.clear()
