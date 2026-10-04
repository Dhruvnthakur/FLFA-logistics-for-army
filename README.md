# Predictive Logistics & Forward Supply Chain (student prototype)

Synthetic-data prototype: demand forecast, stock-risk alerts, route status, dispatch recommendation, map dashboard. See [Problem_Statement.md](Problem_Statement.md), [PRD.md](PRD.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Getting started on your own clone

Everything runs locally against **your own** database, so your seeding and simulator runs never touch anyone else's data.

1. **Clone** the repo (you need read access) and, to share changes, push to your own fork and open a PR.
2. **Database:** create a free Postgres + PostGIS project on [Supabase](https://supabase.com) (or Neon). Copy the *Session pooler* connection string.
3. **Env:** from the repo root, `cp .env.example .env` and set `DATABASE_URL`. Never commit `.env`.
4. **Backend** (Python 3.11+):
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate        # Windows; macOS/Linux: source .venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Seed** (from the repo root, venv active): `python data/generator/seed.py`. This also applies `db/migrations/*.sql`.
6. **Train** the forecast model: `python backend/ml/train.py`.
7. **Run:** `uvicorn app.main:app --reload` in `backend/`, then `npm install && npm run dev` in `frontend/`.

Full command list (tests, simulator, demo script, conventions) is in [CLAUDE.md](CLAUDE.md).

## Using the dashboard

Open http://localhost:5173 (the frontend finds the API through `VITE_API_URL` in the root `.env`, default `http://localhost:8000`). The dashboard refreshes itself every 3 s; the pill in the top bar shows when it last updated.

- **Select** an alert, stock-risk row or dispatch row: the map highlights its route, the Forecast panel shows the one-sentence explanation, actual vs predicted demand, the MAE/MAPE badge and inbound convoys, and the dispatch row is selected. Click again to deselect.
- **Theatre toggle** (map header: Ladakh / Arunachal / Punjab / All, default Ladakh) frames one region so posts don't overlap; selecting a row jumps the map to that post's theatre.
- **Try the demo** (fresh seed, `WEATHER_MODE=sim`): `python simulator/publish.py --scenario drain-post7-diesel --ticks 6`, then close Route A with `PATCH /routes/E9 {"status":"closed"}` (e.g. via http://localhost:8000/docs). Post 7 diesel goes Amber, then Red, and the convoy reroutes via Route B.
- **Stress test: long routes** (fresh seed): `python simulator/publish.py --scenario ladakh-winter --ticks 5` drains every Ladakh post, so the dispatch plan grows from 2 to ~27 rows and Field Depot North's trucks run out; the overflow rides base-depot trucks over multi-hop routes (e.g. BD1 → FD1 → P5 → P6). Close `E1` (Northern Supply Line) and those convoys reroute over the Manali line, about 2.5 days later; close `E17` too and they become unassigned.
- **Reset** after the simulator or route changes: re-run `python data/generator/seed.py`, then restart the API (forecasts are cached per process). The open dashboard picks up the reset within a few seconds.
- **Data is synthetic.** Post names and locations are fictional. The basemap is Esri's light-grey canvas with its reference (place names) overlay; national lines (India's coast and land borders with its direct neighbours only, following India's official map) and state lines come from Natural Earth (`frontend/public/boundaries.geojson`). Neither is authoritative for disputed or administrative boundaries.

## Architecture

```mermaid
flowchart LR
  SIM[IoT simulator<br/>simulator/publish.py] -->|POST /readings| API
  WX[Open-Meteo or sim weather] --> API
  subgraph API[FastAPI on Render]
    FC[Forecast<br/>gradient-boosted model (scikit-learn) + joblib] --> ST[Stock status<br/>Green / Amber / Red + alerts]
    RT[Routing<br/>NetworkX, weather rules] --> ST
    ST --> DP[Dispatch planner<br/>greedy by item priority]
    RT --> DP
    WI[What-if<br/>close route / storm / troops] --> RT
    WI --> FC
  end
  API <--> DB[(Postgres + PostGIS<br/>Supabase)]
  UI[React dashboard on Vercel<br/>polls every 3 s] -->|GET /stock /alerts /routes /dispatch-plan| API
  UI -->|PATCH /routes, POST /whatif| API
```

Data flow: a reading updates stock, days of supply is recomputed from the forecast, the status and alert change, and the dispatch plan is regenerated. Closing a route, or a what-if, re-runs the path search and the plan. The dashboard only reads and polls.

## Deploying

1. **Database:** a Supabase project with PostGIS (the migrations create the extension). Seed it once: `python data/generator/seed.py` (wipes and reloads).
2. **Backend (Render):** create a Blueprint from this repo; `render.yaml` sets the build, start command (`--port $PORT`), health check `/healthz` and Python version. Set `DATABASE_URL` (Supabase session pooler) and `CORS_ORIGINS` (the Vercel URL, no trailing slash; add `http://localhost:5173` for local dev). Migrations run at startup and a background thread warms the demand cache.
3. **Frontend (Vercel):** import the repo with root directory `frontend` and set `VITE_API_URL` to the Render URL.
4. **Before a demo:** the free tier sleeps and the first `/stock` is slow while forecasts warm. Run `python simulator/warmup.py --api https://<your-api>.onrender.com` a few minutes ahead.
5. **Drive it against the hosted API:** `python simulator/publish.py --api https://<your-api>.onrender.com --scenario drain-post7-diesel --ticks 6`, then close Route A (`PATCH /routes/E9`). Re-seed afterwards to reset.

| Variable | Where | Meaning |
|---|---|---|
| `DATABASE_URL` | backend, seed | Postgres connection string |
| `CORS_ORIGINS` | backend | comma-separated browser origins allowed to call the API |
| `WEATHER_MODE` | backend | `sim` (default, deterministic) or `live` (Open-Meteo) |
| `VITE_API_URL` | frontend build | base URL of the API |

Note: local `pytest` runs against whatever `DATABASE_URL` points at and changes route and dispatch state, so use a separate database for tests, or re-seed afterwards.

**If hosting fails (local fallback):** follow *Getting started* above with a local `.env`, run the API (`uvicorn app.main:app` in `backend/`) and `npm run dev` in `frontend/`, then run the demo script from *Using the dashboard*.

## Working rules

Collaborators technically have write access, so by agreement: **never push to `main`**. Work on your own branch (`git checkout -b yourname/topic`), push that branch, and open a PR for the owner to review and merge.
