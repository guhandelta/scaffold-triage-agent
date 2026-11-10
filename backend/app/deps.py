"""Shared FastAPI dependencies, so tests can swap any of them."""

from typing import Annotated

from fastapi import Depends

from app.agent import get_chain
from app.agent.providers import FallbackChain
from app.kb import KnowledgeBase, get_kb
from app.store import TicketStore, get_store

ChainDep = Annotated[FallbackChain, Depends(get_chain)]
StoreDep = Annotated[TicketStore, Depends(get_store)]
KbDep = Annotated[KnowledgeBase, Depends(get_kb)]
