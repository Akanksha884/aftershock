# AFTERSHOCK
*When something goes wrong, know what happens next.*
Agentic incident-recovery platform. Specialised agents (LangGraph) understand an incident, map impact, research, and build a
recovery plan. **Every consequential action needs human approval; all external actions are SIMULATED.**

## Run (local)
    pip install -r backend/requirements.txt
    cd backend && DEMO_PASSWORD=choose-one uvicorn main:app --port 8000
    # React UI:   http://localhost:8000/app/     Classic UI (assets/documents/settings): http://localhost:8000/
    # Login: demo@aftershock.local / <your DEMO_PASSWORD>
Rebuild the React UI: `cd frontend && npm install && npm run build` (outputs to backend/static_react). Dev: `npm run dev` (proxies API to :8000).
Run `npm install` on a normal filesystem (some mounts forbid symlinks).

## Docker
    PG_PASSWORD=.. SECRET_KEY=.. DEMO_PASSWORD=.. docker compose up --build   # Postgres + backend + built React UI, port 80 (/app/)

## Test
    pytest tests          # 16 tests

## Architecture
Incident -> LLM/heuristic summary (validated, retry, fallback) -> LangGraph: Incident -> router -> Security/Finance/Research
(only relevant) -> Recovery -> approval gate -> tool execution (mock) -> verify -> monitoring -> re-plan on rejection.
States: PROPOSED, WAITING_APPROVAL, APPROVED, EXECUTING, VERIFYING, COMPLETED, REJECTED, FAILED, MONITORING (illegal moves -> 409).
Progress = addressed / non-rejected actions. Live updates via SSE. Full audit log.

## Config (.env.example)
DATABASE_URL, LLM_API_KEY (+LLM_MODEL), SEARCH_API_KEY, MAPS_API_KEY, SECRET_KEY, DEMO_PASSWORD, DEMO_MODE.
No LLM key -> DEMO MODE (deterministic, offline).

## Migrations
`cd backend && alembic upgrade head` (tables are also auto-created at startup for local dev).

## Browser acceptance test
`tests/acceptance_browser.py` (Playwright, Chromium): login, analyze, approval card, graph nodes, approve -> completed, reject -> replan,
refresh persistence, document upload, asset add, settings. Start the server on :8080 with DEMO_PASSWORD=x-pass-1 first. Last run: all steps passed, no page errors.

## Known limitations
- Incident graph uses React Flow (click for details, hover highlights paths).
- Search/location tools are local deterministic stubs; the Anthropic call has never run against the live API.
- Image OCR needs the tesseract binary. Auth is simple local signed tokens. Docker setup untested.
- Voice input uses the browser Web Speech API where available. Landing "Security/About" links point to the how-it-works section.
