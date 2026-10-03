# Indian Army – Predictive Logistics & Forward Supply Chain

## 1. The Problem in Plain Words

Forward units (posts in Ladakh, Siachen, Arunachal, the North-East, the Rajasthan desert) depend on a supply chain that runs: **Base Depot → Intermediate/Field Depot → Forward Post**. They need rations, fuel (POL), ammunition, medicines, spares and winter clothing.

Today this chain has three problems:

1. **Data is scattered.** Stock levels, past consumption, vehicle availability, road status and weather forecasts sit in different systems, registers and spreadsheets owned by different people. Nobody has one complete picture.
2. **Planning is reactive.** A post asks for supplies only when it is already running low. In hard terrain a convoy can take days, or the road (passes, landslides, snow) can close completely, so a late request turns into an actual shortage.
3. **Movement isn't optimised.** It is hard to decide which items move first, on which vehicles, by which route, and when, because route closures, weather windows and vehicle capacity are not looked at together.

**The core question:** *Can we predict what each forward post will need, before it needs it, and plan the cheapest safe way to deliver it given the current terrain, weather and transport?*

### Key Stakeholders
| Who | What they need |
|---|---|
| Logistics officer at a depot | What to send, where, and when |
| Forward post commander | Assurance that supplies will arrive before stock runs out |
| Senior planners | One dashboard view of the whole region's risk |

## 2. Breaking Down the "Technology Opportunity"

| Technology | What it means for the prototype |
|---|---|
| **AI/ML demand forecasting** | Predict the next N days of consumption per item per post from past usage, troop strength, season, temperature and activity level |
| **GIS-enabled logistics planning** | Show depots, posts and routes on a map; pick routes that avoid closed or risky roads; estimate travel time by terrain |
| **IoT-based inventory tracking** | Sensors or RFID report stock levels in real time (simulated in the prototype) |
| **Integrated predictive logistics system** | One platform that fuses all of the above and produces alerts and dispatch recommendations |

## 3. What Is Expected from the Prototype

A student prototype does **not** need real Army data or real hardware. Judges expect:

- **A working end-to-end flow:** data comes in → forecast → shortage risk detected → route and dispatch plan suggested → shown on a dashboard.
- **Realistic synthetic data:** generated datasets for posts, depots, items, consumption history, vehicles, routes and weather.
- **A visible AI/ML component** whose output can be explained (e.g. "Post X will run out of fuel in 4 days").
- **A map-based UI**, since GIS is central to the problem.
- **A simulated IoT feed** (a script pushing stock readings) to show the real-time tracking idea.
- **A clear demo story:** for example, "A snowstorm closes Route A. The system re-forecasts, flags Post 7 as critical, and reroutes the convoy through Route B."

## 4. Prototype Features

### 4.1 Demand Forecasting (AI/ML)
- Forecast 7–30 day consumption per post × item (rations, fuel, ammo, medical, spares).
- Inputs: past consumption, troop strength, season and temperature, operational activity level.
- Model: start with Prophet/ARIMA or a Random Forest / XGBoost regressor, and show the forecast against actual values on a chart.
- Output: predicted demand plus **days-of-supply remaining** for each item.

### 4.2 Inventory Tracking (IoT, simulated)
- A simulator script publishes stock readings (MQTT or plain HTTP) from depots and posts.
- Live stock table with colour-coded status: Green (OK), Amber (reorder soon), Red (critical).
- Alerts when stock falls below safety stock or below the predicted need for the lead time.

### 4.3 GIS Logistics Planning
- Interactive map (Leaflet/OpenStreetMap) showing depots, posts and routes.
- Route status overlay: open / degraded / closed, based on weather and terrain.
- Route optimisation (Dijkstra/A* on a road graph, with edge weights from distance, terrain difficulty and weather risk).
- Estimated travel time and a risk score for each route.

### 4.4 Terrain & Weather Integration
- Weather from a free API (Open-Meteo) or a simulated feed.
- Rules that mark routes closed or slower (heavy snow, landslide risk, high altitude).
- Weather also feeds the forecast, since cold weather means more fuel and kerosene use.

### 4.5 Transport & Dispatch Recommendation
- Vehicle fleet with capacity (tonnes) and availability.
- Recommend **what to send, how much, on which vehicle, by which route, and by when**, prioritising critical items (ammo, medical, fuel).
- Simple optimisation: a greedy priority-based load plan, or OR-Tools for a vehicle-routing version.

### 4.6 Integrated Command Dashboard
- One screen with the map, stock-risk table, forecast charts, alerts and recommended dispatches.
- **What-if simulator:** close a route, raise troop strength, or trigger a storm, then watch the forecast and plan update.

## 5. Suggested Tech Stack (student-friendly, deployable)

| Layer | Choice | Deploy on (free tier) |
|---|---|---|
| Frontend | React (JavaScript) + Vite, react-leaflet for maps, Recharts for charts | Vercel / Netlify |
| Backend / API | Python + FastAPI (serves the ML model, routing and alerts) | Render / Railway |
| Database | **PostgreSQL + PostGIS** (stores depot/post locations and routes as geo data, and supports spatial queries) | Supabase or Neon (managed, free) |
| ML | pandas, scikit-learn / XGBoost, Prophet (model saved with joblib and loaded by the API) | runs inside the backend |
| Routing | NetworkX (graph shortest path), optional OR-Tools | runs inside the backend |
| IoT simulation | Python script → REST `POST /readings` (simplest when deployed); MQTT via HiveMQ Cloud is optional | run locally or as a cron job |
| Map tiles | OpenStreetMap via Leaflet | — |
| Weather | Open-Meteo API (free, no key needed) | — |

**Why Postgres + PostGIS rather than SQLite:** free hosts like Render wipe the server's local disk on every redeploy or restart, so an SQLite file would lose its data. A managed Postgres keeps data persistent, lets the API and the IoT simulator write to it at the same time, and PostGIS handles the GIS side natively (distances, nearest depot, route geometry). Supabase also includes realtime subscriptions, so the React dashboard can update live as simulated IoT readings arrive.

## 6. System Flow

```
[Synthetic history + IoT stock feed + Weather API + Route/terrain data]
                         │
                         ▼
              Data integration layer (DB)
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  Demand forecast   Stock-risk calc   Route status/risk
          └──────────────┼──────────────┘
                         ▼
          Dispatch recommendation engine
                         ▼
     Dashboard: map + alerts + forecasts + what-if
```

## 7. Success Criteria for the Demo
1. Forecasts are shown with an accuracy metric (MAE/MAPE) on held-out data.
2. Low-stock alerts fire automatically from the simulated IoT feed.
3. Closing a route on the map changes the recommended plan in real time.
4. A judge can follow one item (e.g. diesel at Post X) from forecast to delivery plan in under 2 minutes.
