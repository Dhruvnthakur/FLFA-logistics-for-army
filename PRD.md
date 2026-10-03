# PRD — Predictive Logistics & Forward Supply Chain (Prototype)

## 1. Problem
Forward posts (Ladakh, Siachen, Arunachal, North-East, Rajasthan) are supplied through **Base Depot → Field Depot → Forward Post**. Today:
1. **Data is scattered** across registers, spreadsheets and separate systems.
2. **Planning is reactive** — posts request supplies only when already low; convoys take days and routes close.
3. **Movement isn't optimised** — routes, weather windows and vehicle capacity aren't considered together.

**Core question:** predict what each post will need before it needs it, and plan the cheapest safe way to deliver it given terrain, weather and transport.

## 2. Goals
- G1. Forecast 7–30 day consumption per post × item and compute days-of-supply.
- G2. Detect shortage risk automatically from a (simulated) real-time stock feed.
- G3. Show the network on a map with live route status and optimal routes.
- G4. Recommend what to send, how much, on which vehicle, by which route, by when.
- G5. Let planners run what-if scenarios and see the plan update live.

## 3. Non-goals
- Real Army data, real sensors/RFID, classified integrations.
- Production auth, RBAC, audit trails.
- Mobile apps, offline mode.
- Full vehicle-routing optimisation (OR-Tools) — optional stretch only.

## 4. Personas
| Persona | Need | Primary screen |
|---|---|---|
| **Depot Logistics Officer** | What to send, where, when | Alerts + Dispatch plan |
| **Forward Post Commander** | Assurance supplies arrive before stock-out | Post view |
| **Senior Planner** | Region-wide risk at a glance; test scenarios | Map + What-if |
| **Demo Operator / Admin** | Seed data, run simulator, trigger scenarios | Admin/what-if panel |

## 5. Functional Requirements

### 5.1 Demand Forecasting (AI/ML)
- **FR-1** Forecast daily consumption for the next 7–30 days per post × item class (rations, fuel/POL, ammo, medical, spares, winter clothing).
- **FR-2** Features: past consumption, troop strength, season, temperature, operational activity level.
- **FR-3** Model: XGBoost / Random Forest regressor (baseline: moving average). Saved with joblib, loaded by the API.
- **FR-4** Report MAE and MAPE on a held-out time window; show forecast vs actual chart.
- **FR-5** Output days-of-supply remaining = current stock ÷ forecast daily demand, plus a one-line explanation.

### 5.2 Inventory Tracking (simulated IoT)
- **FR-6** `POST /readings` accepts stock readings `{location_id, item_id, quantity, timestamp}`; validated and stored.
- **FR-7** Simulator script publishes readings for all depots/posts at a configurable interval, with consumption drift and noise.
- **FR-8** Stock status: **Green** (OK), **Amber** (days-of-supply < lead time + buffer), **Red** (below safety stock or days-of-supply < lead time).
- **FR-9** Alerts are created automatically on status transitions to Amber/Red and de-duplicated while the condition persists.

### 5.3 GIS Logistics Planning
- **FR-10** Map (Leaflet/OSM) shows depots, posts and route segments; markers coloured by worst stock status.
- **FR-11** Route segments coloured open / degraded / closed.
- **FR-12** Route optimisation: NetworkX shortest path with edge weight = f(distance, terrain difficulty, weather risk); closed edges excluded.
- **FR-13** Each route returns estimated travel time and a risk score (0–100).

### 5.4 Terrain & Weather
- **FR-14** Fetch weather per node from Open-Meteo; fall back to simulated weather when offline or `WEATHER_MODE=sim`.
- **FR-15** Rules: heavy snow / high landslide risk → closed; moderate → degraded (speed ×0.5, risk up); altitude raises baseline risk.
- **FR-16** Temperature feeds the forecast (cold → higher fuel/kerosene demand).

### 5.5 Transport & Dispatch
- **FR-17** Vehicle fleet with capacity (tonnes), home depot and availability.
- **FR-18** Greedy priority load plan: order needs by item priority (ammo > medical > fuel > rations > spares > clothing) then urgency (lowest days-of-supply), fill available vehicles by capacity.
- **FR-19** Each recommendation: item, quantity, vehicle, origin depot, route, departure-by time, ETA, and whether it arrives before stock-out.
- **FR-20** Officer can mark a recommendation as approved / dispatched.

### 5.6 Command Dashboard & What-if
- **FR-21** One screen: map, stock-risk table, forecast chart, alerts panel, dispatch table.
- **FR-22** Dashboard refreshes within 5 s of a new reading (Supabase realtime or polling).
- **FR-23** What-if: close/open a route, trigger a storm over a region, change troop strength at a post → forecast, alerts and plan recompute.
- **FR-24** Show before/after diff of the dispatch plan for a what-if.
- **FR-25** Post view: one post's stock, days-of-supply and inbound convoys.

## 6. Data Model (summary)
| Table | Key fields |
|---|---|
| `locations` | id, name, kind (base_depot/field_depot/post), region, altitude_m, troop_strength, activity_level (posts only), geom Point — depots and posts share one table so every `location_id` has a single FK |
| `items` | id, name, class, unit, weight_kg_per_unit, priority |
| `stock_levels` | location_id, item_id, quantity, safety_stock, updated_at |
| `stock_readings` | id, location_id, item_id, quantity, ts |
| `consumption_history` | post_id, item_id, date, qty, troop_strength, temp_c, activity_level |
| `route_edges` | id, from_node, to_node, distance_km, terrain_difficulty, base_speed_kmh, status, geom LineString |
| `weather` | node_id, ts, temp_c, snowfall_cm, precip_mm, wind_kmh |
| `vehicles` | id, type, capacity_t, depot_id, available |
| `alerts` | id, location_id, item_id, level, message, created_at, resolved_at |
| `dispatch_plans` | id, item_id, qty, vehicle_id, origin, destination, path, depart_by, eta, status |

## 7. API Surface
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/locations` | Depots + posts (GeoJSON) |
| GET | `/stock` | Current stock + status per location × item |
| POST | `/readings` | Ingest IoT reading |
| GET | `/forecast/{post_id}/{item_id}?days=14` | Forecast series, days-of-supply, explanation |
| GET | `/forecast/metrics` | MAE/MAPE on holdout |
| GET | `/routes` | Edges with status, ETA, risk (GeoJSON) |
| PATCH | `/routes/{id}` | Set status open/degraded/closed |
| GET | `/alerts` | Active alerts |
| GET | `/dispatch-plan` | Current recommendations |
| PATCH | `/dispatch-plan/{id}` | Approve / mark dispatched |
| POST | `/whatif` | Apply scenario, return before/after plan |
| POST | `/whatif/reset` | Restore baseline |

## 8. Non-functional Requirements
- Deployable on free tiers (Vercel, Render, Supabase/Neon); no local-disk state.
- API p95 < 1 s for dashboard endpoints on seeded data.
- Dashboard reflects new readings within 5 s.
- Works on laptop screens (≥1280px); readable on a projector.
- All data synthetic; repo contains no real locations of units.

## 9. Success Metrics (demo)
1. Forecast MAE/MAPE shown on held-out data.
2. Low-stock alerts fire automatically from the simulator feed.
3. Closing a route on the map changes the recommended plan in real time.
4. A judge can trace diesel at Post 7 from forecast to delivery plan in < 2 minutes.

## 10. Risks & Assumptions
| Risk | Mitigation |
|---|---|
| Render free tier cold starts (~30–60 s) | Warm-up ping before demo; keep a local run as backup |
| Open-Meteo unavailable | `WEATHER_MODE=sim` fallback |
| Synthetic data too clean → unrealistic accuracy | Add noise, holidays, surge events, missing readings |
| Scope creep (MQTT, VRP, auth) | Deferred list in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) |

Assumptions: one region (~3 depots, ~10 posts) is enough to tell the story; daily granularity is sufficient for forecasting.
