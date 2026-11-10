from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.config import get_settings
from app.deps import ChainDep, KbDep
from app.routers import tickets, triage
from app.schemas import Health


def _operation_id(route: APIRoute) -> str:
    # Clean names in the generated client: `triage`, not `triage_api_triage_post`.
    return route.name


app = FastAPI(
    title="Triage Agent API",
    version="0.1.0",
    generate_unique_id_function=_operation_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(triage.router)
app.include_router(tickets.router)


@app.get("/api/health", response_model=Health, tags=["meta"])
async def health(chain: ChainDep, kb: KbDep) -> Health:
    """Which agents are active, in fallback order, and how many doc sections they can read."""
    agent = " > ".join(p.name for p in chain.providers)
    return Health(status="ok", agent=agent, docs=len(kb.sections))
