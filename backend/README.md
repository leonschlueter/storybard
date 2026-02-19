# Storybard Engine (Dev)

A production-shaped, modular FastAPI backend for an LLM-driven TTRPG campaign engine with deterministic mechanics.

## Features (current dev scope)
- **Explore / Downtime / Battle (stub) modes**
- **Deterministic mechanics**: encumbrance (STR*15), skill modifiers, roll resolution
- **PhaseChecker**: decides whether a roll is required (skill check or initiative request)
- **Ollama Structured Outputs** everywhere (Pydantic schemas + JSON schema `format`)
- **Campaign Seeder** (LLM): generates medium-sized world, lore facts, NPCs, story threads, starter items/spells
- **Story threads**: checked every 3 turns (LLM)
- **Memory regression** every turn + **campaign summary** every 5 turns
- **Timeline**: calendar start date + in-game current datetime; events store campaign timestamp
- **Observability**: structured logs, Prometheus metrics, OpenTelemetry traces (optional exporter)

No frontend is included yet. A simple CLI bash script is included for testing.

---

## Requirements
- Python 3.11+ (3.12 ok)
- Postgres (via Docker compose below)
- Ollama running locally (default http://localhost:11434) with your model pulled (default `mistral`)

---

## Quickstart

### 1) Create venv + install deps
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Start Postgres
```bash
docker compose up -d db
```

### 3) Configure env
```bash
cp .env.example .env
# edit DATABASE_URL if needed
```

### 4) Run API
```bash
uvicorn app.main:app --reload
```

### 5) Run CLI play loop (auto-seeds every run)
```bash
bash cli/play_campaign.sh
```

OpenAPI docs:
- http://127.0.0.1:8000/docs

Metrics:
- http://127.0.0.1:8000/metrics

---

## Notes
- Defaults assume Ollama is available at `http://localhost:11434`. Set `OLLAMA_BASE_URL` to override.
- OpenTelemetry exporter is optional. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to enable OTLP export.

