import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const API = import.meta.env.VITE_API_URL

// API status words → chip tone + label. Stock: green/amber/red; routes: open/degraded/closed.
const TONE = { green: 'ok', amber: 'warn', red: 'crit', open: 'ok', degraded: 'warn', closed: 'crit' }
const RANK = { green: 0, amber: 1, red: 2 }
const label = (s) => s[0].toUpperCase() + s.slice(1)
// marker size doubles as a non-colour cue; the legend swatches use the same diameters (index.css .key)
const RADIUS = { green: 6, amber: 8, red: 10 }

function Chip({ status }) {
  return <span className={`chip ${TONE[status]}`}>{label(status)}</span>
}

// Worst stock row per post (by status, then fewest days of supply): drives marker colour and popup sentence.
function worstByPost(stock) {
  const worst = {}
  for (const r of stock) {
    if (r.kind !== 'post') continue
    const w = worst[r.location_id]
    if (!w || RANK[r.status] > RANK[w.status] || (r.status === w.status && r.days_of_supply < w.days_of_supply)) worst[r.location_id] = r
  }
  return worst
}

// Frames the map on the posts/depots so the network, not the surrounding country, fills the view.
function FitBounds({ points }) {
  const map = useMap()
  useEffect(() => {
    if (!points.length) return
    const fit = () => {
      map.invalidateSize()
      map.fitBounds(points, { padding: [32, 32], maxZoom: 8, animate: false })
    }
    // the flex panel settles after the map mounts, so refit whenever its container resizes
    const ro = new ResizeObserver(fit)
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map, points])
  return null
}

function Panel({ title, className = '', children }) {
  return (
    <section className={`panel ${className}`}>
      <h2>{title}</h2>
      <div className="panel-body">{children}</div>
    </section>
  )
}

// Departures-board grammar shared by Alerts, Dispatch and Stock risk: header row + hairline rows.
// `grid` is the column template shared by header and rows; column `num` is the right-aligned time column.
function Board({ title, cols, grid, num, empty }) {
  return (
    <Panel title={title}>
      <div className="board-head" style={{ '--grid': grid }} role="presentation">
        {cols.map((c, i) => (
          <span key={c || i} className={i === num ? 'num' : undefined}>
            {c}
          </span>
        ))}
      </div>
      <p className="empty">{empty}</p>
    </Panel>
  )
}

export default function App() {
  const [health, setHealth] = useState('Checking API…')
  const [places, setPlaces] = useState([])
  const [routes, setRoutes] = useState([])
  const [stock, setStock] = useState([])
  const points = useMemo(() => places.map((p) => p.latlng), [places])
  const worst = useMemo(() => worstByPost(stock), [stock])

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then((d) => setHealth(d.status === 'ok' ? `API ok · PostGIS ${d.postgis}` : `API error: ${d.db}`))
      .catch(() => setHealth('API unreachable'))
    fetch(`${API}/locations`)
      .then((r) => r.json())
      .then((d) =>
        setPlaces(
          d.features.map((f) => ({
            id: f.properties.id,
            name: f.properties.name,
            kind: f.properties.kind,
            region: f.properties.region,
            latlng: [f.geometry.coordinates[1], f.geometry.coordinates[0]],
          })),
        ),
      )
      .catch(() => {})
    fetch(`${API}/routes`)
      .then((r) => r.json())
      .then((d) =>
        setRoutes(d.features.map((f) => ({ ...f.properties, line: f.geometry.coordinates.map(([lng, lat]) => [lat, lng]) }))),
      )
      .catch(() => {})
    fetch(`${API}/stock`)
      .then((r) => r.json())
      .then((d) => setStock(d.stock))
      .catch(() => {})
  }, [])

  return (
    <div className="app">
      <header className="topbar">
        <h1>Forward Logistics Command</h1>
        <span className="pill" role="status">
          {health}
        </span>
      </header>
      <main className="board">
        <section className="panel map-panel">
          <h2>Network map</h2>
          {/* fallback view until /locations arrives: northern India (Ladakh / Arunachal span) */}
          <MapContainer center={[31, 85]} zoom={5} zoomSnap={0.25} zoomControl={false}>
            <TileLayer
              attribution="Tiles &copy; Esri"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            />
            <FitBounds points={points} />
            {/* status lives in the class (colour + dash in index.css); keyed on status because Leaflet sets className only once */}
            {routes.map((r) => (
              <Polyline key={`${r.id}-${r.status}`} positions={r.line} pathOptions={{ className: `route ${r.status}` }}>
                <Popup maxWidth={280} autoPanPadding={[24, 24]}>
                  <strong>{r.name}</strong> <Chip status={r.status} />
                  <p>
                    {r.distance_km} km · ETA {r.eta_hours} h · risk {r.risk}
                  </p>
                  {r.weather_reason && <p>{r.weather_reason}</p>}
                </Popup>
              </Polyline>
            ))}
            {places.map((p) => {
              const w = worst[p.id]
              return (
                <CircleMarker
                  key={`${p.id}-${w?.status ?? 'depot'}`}
                  center={p.latlng}
                  radius={RADIUS[w?.status] ?? 6}
                  pathOptions={{ className: w ? `marker ${w.status}` : 'marker depot' }}
                >
                  {/* posts cluster tightly at network zoom, so only at-risk posts carry a standing name, with the status word */}
                  <Tooltip permanent={!!w && w.status !== 'green'} direction="right" offset={[10, 0]} className="map-label">
                    {w && w.status !== 'green' ? `${p.name} · ${label(w.status)}` : p.name}
                  </Tooltip>
                  <Popup maxWidth={280} autoPanPadding={[24, 24]}>
                    <strong>{p.name}</strong> {w && <Chip status={w.status} />}
                    <p>{p.region}</p>
                    {w && <p>{w.explanation}</p>}
                    {routes
                      .filter((r) => r.to === p.id)
                      .map((r) => (
                        <p key={r.id}>
                          Inbound {r.name}: {r.status}, ETA {r.eta_hours} h, risk {r.risk}
                        </p>
                      ))}
                  </Popup>
                </CircleMarker>
              )
            })}
          </MapContainer>
          <ul className="legend" aria-label="Map legend">
            <li><span className="key green" />Green</li>
            <li><span className="key amber" />Amber</li>
            <li><span className="key red" />Red</li>
            <li><span className="key depot" />Depot</li>
            <li><span className="key line open" />Open</li>
            <li><span className="key line degraded" />Degraded</li>
            <li><span className="key line closed" />Closed</li>
          </ul>
        </section>
        <div className="side">
          <Board
            title="Alerts"
            cols={['Post', 'Item', 'Status', 'Days left']}
            grid="4rem 1fr 5.5rem 4.5rem"
            num={3}
            empty="No stock-risk alerts. Posts with low supply appear here."
          />
          <Board
            title="Dispatch plan"
            cols={['Post', 'Item', 'Vehicle', 'ETA', '']}
            grid="4rem 1fr 4.5rem 4rem 5.25rem"
            num={3}
            empty="No convoys recommended. Approved departures appear here."
          />
        </div>
        <div className="bottom">
          <Panel title="Forecast">
            <p className="empty">Select an alert to see its forecast.</p>
          </Panel>
          <Board
            title="Stock risk"
            cols={['Post', 'Item', 'Status', 'Days left']}
            grid="4rem 1fr 5.5rem 4.5rem"
            num={3}
            empty="Days of supply per post and item appear here."
          />
        </div>
      </main>
    </div>
  )
}
