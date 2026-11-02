from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.config import get_settings
from app.routers import triage
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


@app.get("/api/health", response_model=Health, tags=["meta"])
async def health() -> Health:
    return Health(status="ok", agent="rules")
