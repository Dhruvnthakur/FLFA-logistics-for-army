# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Status:** Phases 0–4 done (schema, synthetic data, `GET /locations`, forecasting + `/forecast`, `POST /readings`, `/stock`, `/alerts`, IoT simulator, weather + `GET/PATCH /routes` with NetworkX paths). Track progress in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Project
Student prototype of a **Predictive Logistics & Forward Supply Chain** system for Indian Army forward posts. Pipeline: synthetic data + simulated IoT stock feed + weather → demand forecast → stock-risk alerts → route status/optimisation → dispatch recommendation → map-based command dashboard with a what-if simulator.

Source docs (read before changing scope):
- [Problem_Statement.md](Problem_Statement.md) — the brief and success criteria
- [PRD.md](PRD.md) — requirements (FR-x IDs referenced in commits/PRs)
- [USER_FLOWS.md](USER_FLOWS.md) — flows per user type
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — phase checklist; tick boxes as work lands

## Stack (fixed — don't swap without asking)
| Layer | Choice |
|---|---|
| Frontend | React (JavaScript) + Vite, react-leaflet, Recharts → Vercel |
| Backend | Python + FastAPI → Render |
| DB | PostgreSQL + PostGIS on Supabase (or Neon) |
| ML | pandas, scikit-learn / XGBoost, joblib |
| Routing | NetworkX |
| Weather | Open-Meteo (no key) with simulated fallback |
| IoT sim | Python script → `POST /readings` |

## Layout (planned)
```
frontend/            React app
backend/app/api/     FastAPI routers
backend/app/services/ forecasting, stock risk, routing, dispatch logic
backend/app/db.py    DB connection
backend/ml/          training script + artifacts/ (joblib models)
data/generator/      synthetic data generator + seed script
simulator/           IoT stock-reading publisher
db/migrations/       SQL schema (PostGIS)
```

## Commands
Env: one `.env` at repo root (copy `.env.example`); backend loads it via python-dotenv, Vite via `envDir: '..'`.
Backend venv lives in `backend/.venv` (Windows: `backend\.venv\Scripts\activate`).
- Backend setup: `pip install -r requirements.txt` (in `backend/`, venv active)
- Backend dev: `uvicorn app.main:app --reload` (in `backend/`) → http://localhost:8000/health
- Frontend dev: `npm run dev` (in `frontend/`) → http://localhost:5173
- Frontend build: `npm run build` (in `frontend/`)
- Seed (also applies `db/migrations/*.sql`, which are idempotent): `python data/generator/seed.py` (from repo root, backend venv active)
- Generator self-check (no DB): `python data/generator/generate.py`
- Tests: `python -m pytest` (in `backend/`; needs a live `DATABASE_URL`); single test: `python -m pytest tests/test_health.py::test_health_reports_db_and_postgis`
- Train (also run after re-seeding; ~45s; artifacts in `backend/ml/artifacts/` are committed for Render): `python backend/ml/train.py` (repo root)
- Simulator (API running; stdlib only): `python simulator/publish.py` (`--api URL`, `--interval 5`, `--ticks N`); demo: `--scenario drain-post7-diesel` (P7 diesel Green → Amber → Red in ~6 ticks). It mutates stock — re-seed to reset.
- Status thresholds (handling days, driving hours/day, buffer) live only in `backend/app/services/stock.py`; `/stock` serves them. Lead time per post = handling days + best-route ETA (`services/routing.py`). Route rules (snow/precip/wind → degraded/closed) live in `routing.py`; effective edge status = worse of manual `PATCH /routes/{id}` and weather. `PATCH` re-syncs all alerts.
- Weather: `WEATHER_MODE=sim` (default, deterministic, never closes a road by itself) or `live` (Open-Meteo, cached 30 min, falls back to sim on error). Tests force sim. Demand forecasts are cached per process — restart the API after re-seed/retrain.

## Data flow (how the pieces connect)
`POST /readings` updates stock → days-of-supply recomputed from the forecast → Green/Amber/Red status → alert raised → dispatch plan regenerated. `PATCH /routes/{id}` or `POST /whatif` changes edge status/weather → NetworkX re-pathfinds → dispatch plan regenerated. The dashboard only reads (`/stock`, `/alerts`, `/routes`, `/dispatch-plan`) and polls every ≤5s. Full endpoint list: PRD §7; tables: PRD §6.

## Conventions
- **Synthetic data only.** Never add real Army locations, unit names or data. Use plausible regions (Ladakh, Arunachal, etc.) with fictional post names (Post 1..N).
- **No SQLite.** Render wipes local disk; all state lives in Postgres.
- Geo columns use PostGIS `geography(Point, 4326)` / `geography(LineString, 4326)`.
- Config via env vars only: `DATABASE_URL`, `VITE_API_URL`, `WEATHER_MODE=live|sim`. Keep `.env.example` current; never commit `.env`.
- Stock status thresholds (Green / Amber / Red) and item priority (ammo > medical > fuel > rations > spares > clothing) are defined **once** in the backend and served to the frontend — no duplicated constants.
- Every forecast shown in the UI must be explainable in one sentence, e.g. "Post 7 runs out of diesel in 4 days".
- Keep it simple: plain functions over class hierarchies; one service module per concern.
- Validate all input at `POST /readings` and `POST /whatif` (trust boundary).

## Scope guardrails
In scope: the core pipeline above. **Deferred / optional:** MQTT (HiveMQ), OR-Tools VRP, Prophet comparison, auth/RBAC, mobile app. Don't build these unless the core demo is done and the user asks.

## The demo to protect
"A snowstorm closes Route A → system re-forecasts → Post 7 flagged critical → convoy rerouted via Route B." Any change that breaks this end-to-end story is a regression.

Script (fresh seed, `WEATHER_MODE=sim`, API restarted): P7 diesel starts Green (~9.7 days of supply; lead time 2.8 days via Route A). Run `python simulator/publish.py --scenario drain-post7-diesel --ticks 6` → Amber at ~3–4.5 days. Then `PATCH /routes/E9 {"status":"closed"}` → lead time 4.6 days via Route B (E7 → E10) → P7 diesel flips Red. Closing Route A on a fresh seed alone leaves it Green — drain first. Re-seed to reset. A judge must be able to trace one item (e.g. diesel at Post 7) from forecast to delivery plan in under 2 minutes.
