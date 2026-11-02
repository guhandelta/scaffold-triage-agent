from functools import lru_cache

from app.agent.providers import FallbackChain, build_chain
from app.config import get_settings


@lru_cache
def get_chain() -> FallbackChain:
    return build_chain(get_settings())


__all__ = ["FallbackChain", "get_chain"]
