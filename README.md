# Triage Agent

A support ticket triage agent you can reconfigure for any organization. For each ticket it reads
your support docs, then either drafts a reply that cites the doc sections it used, or hands the
ticket to a person. Reviewers can confirm, override, note, assign and resolve, depending on their
role.

```
backend/    FastAPI API (Python 3.13, uv): routing, doc retrieval, model fallback, review, upload
frontend/   Vite + React, TanStack Router and Query, Tailwind, shadcn/ui
examples/   A second organization's config and docs, to copy from
```

## Run it with Docker

```bash
docker compose up --build        # then open http://localhost:8080
```

Tickets are kept in a Docker volume, so they survive restarts. Model keys are read from
`backend/.env` when it exists (`ANTHROPIC_API_KEY`, `OPEN_AI_API_KEY`, `GOOGLE_API_KEY`). With no
keys, offline rules answer straight from the docs.

## Make it yours

Everything an organization changes lives in one folder: a `triage.yaml` and its docs.

1. Copy `examples/acme-hosting` to a folder of your own.
2. Edit `triage.yaml`:
   - `organization`: your name and product, used in the agent's prompt and the header.
   - `docs`: where your docs are (relative to the file) and how many sections to read per ticket.
   - `routing.human_only`: phrases that always go to a person, before any model sees the ticket.
   - `agent`: which models to try and in what order, and extra guidance for the prompt.
   - `replies`: the greeting and closing for replies the offline rules write.
   - `access`: what each role may do, and who the app acts as without sign-in.
3. Write your docs in Markdown. Each `## Section` is something the agent can cite. Start a section
   with `> Handled by a person.` to keep the agent from ever answering it. Put rules for the agent
   (never sent to customers) under `policies/`. See `backend/data/docs/README.md`.
4. Check it, then run it:

```bash
cd backend && uv run python -m app.org_config ../my-org/triage.yaml
ORG_DIR=./my-org docker compose up --build
```

After editing the folder, `docker compose restart api` picks up the changes. Run each
organization as its own compose project (`docker compose -p my-org ...`) to keep their tickets
apart.

Secrets never go in `triage.yaml`. The environment can also override `PROVIDER_ORDER`,
`CLAUDE_MODEL`, `OPENAI_MODEL`, `GOOGLE_MODEL` and `DOCS_PATH` for quick experiments.

## Run it for development

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload     # API on :8000
cd frontend && npm install --legacy-peer-deps && npm run dev      # UI on :5173, proxies /api
```

The API reads `backend/triage.yaml` unless `TRIAGE_CONFIG` points elsewhere.

## Checks

```bash
cd backend && uv run ruff check . && uv run pytest              # 100% coverage required
cd frontend && npm run test:coverage && npm run lint && npm run build
cd backend && uv run python scripts/live_check.py              # one call to each keyed model
```

After changing the API, run `npm run gen:api` in `frontend` to regenerate the typed client.

## Sign-in

There is no sign-in yet. The name and role picker in the header sends `X-User-Name` and
`X-User-Role`, which the API trusts. Before exposing the app beyond a trusted network, replace
`get_current_user` in `backend/app/auth.py` with your organization's sign-in.
