# Implementation Plan

Phase-wise checklist. Tick boxes as work lands. FR IDs refer to [PRD.md](PRD.md). Each phase ends with a **Done when** check — don't start the next phase until it passes.

---

## Phase 0 — Setup
- [x] Create folders: `frontend/`, `backend/`, `data/generator/`, `simulator/`, `db/migrations/`
- [x] Create Supabase (or Neon) project; enable `postgis` extension (`db/migrations/001_postgis.sql`)
- [x] Backend: FastAPI app with `GET /health`, `requirements.txt`, DB connection from `DATABASE_URL`
- [x] Frontend: Vite + React app; install `react-leaflet`, `leaflet`, `recharts`
- [x] `.env.example` (`DATABASE_URL`, `VITE_API_URL`, `WEATHER_MODE`); `.gitignore` for `.env`, `node_modules`, `__pycache__`
- [x] Fill in the **Commands** section of [CLAUDE.md](CLAUDE.md)

**Done when:** `/health` returns OK against the hosted DB and the Vite app loads a blank Leaflet map.

---

## Phase 1 — Data model & synthetic data
- [x] SQL migration for all tables in PRD §6 (PostGIS geography columns)
- [x] Generator: ~3 depots (1 base, 2 field), ~10 posts across 2 regions with realistic lat/lon & altitude
- [x] Items: rations, fuel/POL, ammo, medical, spares, winter clothing (with priority + weight)
- [x] 2 years of daily consumption per post × item driven by troop strength, season, temperature, activity level, plus noise and surge events
- [x] Road graph: depot → field depot → post edges with distance, terrain difficulty, base speed, LineString geometry; include at least one alternate path (Route A / Route B to Post 7)
- [x] Vehicle fleet with capacities and home depots
- [x] Initial stock levels + safety stock
- [x] `seed.py` that wipes and reloads everything idempotently

**Done when:** one command seeds the DB and `GET /locations` returns GeoJSON with all depots and posts.

---

## Phase 2 — Demand forecasting (FR-1 … FR-5, FR-16)
- [x] Feature builder: lags (1, 7, 14), rolling means, day-of-year, troop strength, temperature, activity level
- [x] Baseline: 7-day moving average
- [x] Train XGBoost (or Random Forest) on all but the last 60 days; evaluate on held-out 60 days
- [x] Record MAE + MAPE vs baseline; save model + metrics with joblib/JSON to `backend/ml/artifacts/`
- [x] Forecast service: recursive N-day forecast (7–30) per post × item
- [x] Days-of-supply + one-line explanation string
- [x] Endpoints: `GET /forecast/{post_id}/{item_id}`, `GET /forecast/metrics`
- [x] Test: forecast length = N, days-of-supply math on a fixed example

**Done when:** model beats the moving-average baseline on MAPE and the API returns "Post 7 runs out of diesel in X days".

---

## Phase 3 — IoT inventory & alerts (FR-6 … FR-9)
- [x] `POST /readings` with validation (known location/item, quantity ≥ 0, sane timestamp)
- [x] Update `stock_levels` on each reading
- [x] Status function (Green/Amber/Red) — single source of truth, uses days-of-supply, safety stock and lead time
- [x] Alert creation on transitions; de-duplicate open alerts; resolve on recovery
- [x] `GET /stock`, `GET /alerts`
- [x] Simulator script: loops over locations, applies consumption + noise, POSTs readings every N seconds; `--scenario drain-post7-diesel` flag for the demo
- [x] Test: status thresholds and alert de-duplication

**Done when:** running the simulator makes Post 7 diesel go Amber → Red and an alert appears in `GET /alerts` without manual steps.

---

## Phase 4 — Weather, routes & GIS (FR-10 … FR-15)
- [x] Open-Meteo client (current + 3-day forecast per node), `WEATHER_MODE=sim` fallback generator
- [x] Rule engine: snowfall / precipitation / wind / altitude → open / degraded / closed + risk score
- [x] Edge weight = distance ÷ effective speed × (1 + risk factor); closed edges removed
- [x] NetworkX graph built from `route_edges`; shortest path depot → post with ETA and risk
- [x] Lead time for stock status now comes from best-route ETA
- [x] `GET /routes` (GeoJSON with status, ETA, risk), `PATCH /routes/{id}`
- [x] Test: closing Route A makes the path to Post 7 use Route B

**Done when:** `PATCH` Route A to closed → `GET /routes` path for Post 7 switches to Route B with a higher ETA.

---

## Phase 5 — Dispatch recommendation (FR-17 … FR-20)
- [ ] Compute needs: for each post × item, qty to cover lead time + target days-of-supply − current stock
- [ ] Sort by item priority, then lowest days-of-supply
- [ ] Greedy assignment to available vehicles at the nearest depot (by route ETA) respecting capacity (tonnes)
- [ ] Output: item, qty, vehicle, origin, path, depart-by, ETA, arrives-before-stock-out flag
- [ ] Persist plan; `GET /dispatch-plan`, `PATCH /dispatch-plan/{id}` (approved/dispatched)
- [ ] Re-run planner on stock status change, route change, or what-if
- [ ] Test: ammo/medical scheduled before rations when capacity is short

**Done when:** the plan for Post 7 diesel lists a vehicle, route and ETA, and changes when Route A closes.

---

## Phase 6 — Command dashboard (FR-21, FR-22, FR-25)
- [ ] Layout: map (left/centre), alerts + dispatch tables (right), forecast chart (bottom)
- [ ] Map: depot/post markers coloured by worst status; route polylines coloured by status; popup with ETA/risk
- [ ] Stock-risk table with Green/Amber/Red badges, sortable by days-of-supply
- [ ] Forecast chart: actual vs predicted + holdout MAE/MAPE badge
- [ ] Alerts panel → click selects post/item and highlights route and dispatch row
- [ ] Dispatch table with Approve / Dispatched buttons
- [ ] Post view (single post: stock, days-of-supply, inbound convoys)
- [ ] Live refresh: Supabase realtime on `stock_levels`/`alerts`, or 3 s polling
- [ ] Projector check: readable at 1280px, colour + label (not colour alone) for status

**Done when:** a new simulator reading shows up on the dashboard within 5 s, and clicking an alert walks forecast → route → dispatch.

---

## Phase 7 — What-if simulator (FR-23, FR-24)
- [ ] `POST /whatif` scenarios: `close_route`, `storm(region)`, `troop_change(post, strength)`
- [ ] Snapshot current plan, apply scenario, re-run forecast → status → routing → dispatch
- [ ] Return before/after diff (rerouted items, ETA changes, new Red posts)
- [ ] `POST /whatif/reset` restores baseline
- [ ] UI panel: scenario picker, Run, Reset, diff view; map updates live
- [ ] Test: storm over Route A region closes it and diff shows reroute

**Done when:** the full demo story (storm → Route A closed → Post 7 Red → reroute via Route B) runs from the UI.

---

## Phase 8 — Deploy & demo
- [ ] Backend on Render (start command, env vars, model artifact included)
- [ ] Frontend on Vercel with `VITE_API_URL`
- [ ] CORS locked to the Vercel domain
- [ ] Simulator runs locally or as a scheduled job against the hosted API
- [ ] Warm-up script for Render cold start
- [ ] README: architecture diagram, setup, demo script
- [ ] Rehearse demo against PRD §9 success metrics; time it (< 2 min)
- [ ] Local fallback run tested in case hosting fails

**Done when:** all four success metrics pass on the deployed URLs.

---

## Optional / Deferred (only after Phase 8)
- [ ] MQTT via HiveMQ Cloud for the simulator
- [ ] OR-Tools vehicle-routing version of the dispatch planner
- [ ] Prophet model comparison
- [ ] Auth / role-based views
- [ ] Nearest-depot spatial queries via PostGIS `ST_Distance` in the UI
