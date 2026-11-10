from functools import lru_cache

from app.agent.providers import FallbackChain, build_chain
from app.config import get_settings
from app.org_config import get_org_config


@lru_cache
def get_chain() -> FallbackChain:
    return build_chain(get_settings(), get_org_config())


__all__ = ["FallbackChain", "get_chain"]
