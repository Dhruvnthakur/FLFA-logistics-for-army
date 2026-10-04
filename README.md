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

Open http://localhost:5173 (the frontend finds the API through `VITE_API_URL` in the root `.env`, default `http://localhost:8000`).

- **Select** an alert, stock-risk row or dispatch row: the map highlights its route, the Forecast panel shows the one-sentence explanation, actual vs predicted demand, the MAE/MAPE badge and inbound convoys, and the dispatch row is selected. Click again to deselect.
- **Theatre toggle** (map header: Ladakh / Arunachal / Punjab / All, default Ladakh) frames one region so posts don't overlap; selecting a row jumps the map to that post's theatre.
- **Try the demo** (fresh seed, `WEATHER_MODE=sim`): `python simulator/publish.py --scenario drain-post7-diesel --ticks 6`, then close Route A with `PATCH /routes/E9 {"status":"closed"}` (e.g. via http://localhost:8000/docs). Post 7 diesel goes Amber, then Red, and the convoy reroutes via Route B.
- **Reset** after the simulator or route changes: re-run `python data/generator/seed.py`, then restart the API (forecasts are cached per process).
- **Data is synthetic.** Post names and locations are fictional. The basemap is Esri's light-grey canvas with its reference (place names) overlay; national lines (India's coast and land borders with its direct neighbours only, following India's official map) and state lines come from Natural Earth (`frontend/public/boundaries.geojson`). Neither is authoritative for disputed or administrative boundaries.

## Working rules

Collaborators technically have write access, so by agreement: **never push to `main`**. Work on your own branch (`git checkout -b yourname/topic`), push that branch, and open a PR for the owner to review and merge.
