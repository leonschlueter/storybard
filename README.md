# Storybard

An LLM-driven narrative engine and world simulation — see `spec/spec.md` for the full
design. Currently in **Phase 1: walking skeleton** — a minimal 4-node steerable chain
(Intent Parse → Plausibility Check → Mechanical Check → Narrator) proven end to end against
a real local model, before building out the rest of the spec's breadth. See
`.claude/plans/` history or ask for the current implementation plan for what's next.

## Requirements

- [LM Studio](https://lmstudio.ai) running on your host, local server started (Settings >
  Local Server > Start), with a chat model loaded. Confirm the exact model id with
  `curl http://localhost:1234/v1/models` and set `LLM_MODEL_DEFAULT` in `server/.env` to
  match.
- Docker + Docker Compose.

## Quickstart

```bash
cp server/.env.example server/.env   # edit LLM_MODEL_DEFAULT to match your loaded model
cp web/.env.example web/.env
docker compose up -d --build
cd server && uv run alembic upgrade head   # first run only, or after a schema change
```

- Frontend (walking skeleton UI): http://localhost:5173
- API: http://localhost:8000 (docs at `/docs`)
- pgAdmin: http://localhost:5050 (opens straight in, "Storybard DB" connection preloaded)

## Repo layout

```
server/   Python: FastAPI + LangGraph + SQLAlchemy (async) + Postgres/pgvector
web/      React + Vite + TypeScript
spec/     Design docs — spec.md is the source of truth
```

## Development

```bash
cd server && uv run pytest              # backend tests
cd web && pnpm exec tsc -b              # frontend typecheck
```
