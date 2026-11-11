"""Shared FastAPI dependencies, so tests can swap any of them."""

from typing import Annotated

from fastapi import Depends

from app.agent import get_chain
from app.agent.providers import FallbackChain
from app.kb import KnowledgeBase, get_kb
from app.org_config import OrgConfig, get_org_config
from app.people import PeopleStore, get_people_store
from app.store import TicketStore, get_store

ChainDep = Annotated[FallbackChain, Depends(get_chain)]
StoreDep = Annotated[TicketStore, Depends(get_store)]
KbDep = Annotated[KnowledgeBase, Depends(get_kb)]
ConfigDep = Annotated[OrgConfig, Depends(get_org_config)]
PeopleDep = Annotated[PeopleStore, Depends(get_people_store)]
