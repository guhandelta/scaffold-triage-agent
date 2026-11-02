# Triage Agent

Phase 0: a working path from a ticket to a decision. Rules decide reply or escalate, with no model yet.

```
backend/   FastAPI API (Python 3.13, uv)
frontend/  Vite + React, TanStack Router and Query, Tailwind, shadcn/ui components
```

## Run it

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload     # API on :8000
cd frontend && npm install && npm run dev                          # UI on :5173, proxies /api
```

## Checks

```bash
cd backend && uv run ruff check . && uv run pytest
cd frontend && npm run build
```

## After changing the API

```bash
cd frontend && npm run gen:api   # exports openapi.json and regenerates src/client
```

Next phases add the model-backed agent, per-ticket memory, tools, routing and an escalation queue.
