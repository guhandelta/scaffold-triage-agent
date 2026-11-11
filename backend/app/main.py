from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.config import get_settings
from app.deps import ChainDep, ConfigDep, KbDep
from app.routers import approvals, people, tickets, triage
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
app.include_router(people.router)
app.include_router(approvals.router)


@app.get("/api/health", response_model=Health, tags=["meta"])
async def health(chain: ChainDep, kb: KbDep, config: ConfigDep) -> Health:
    """Who the agent works for, which models are active in fallback order, and how many doc
    sections they can read."""
    agent = " > ".join(p.name for p in chain.providers)
    return Health(
        status="ok", organization=config.organization.name, agent=agent, docs=len(kb.sections)
    )
