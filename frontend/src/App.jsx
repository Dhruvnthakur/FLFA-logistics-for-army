import { Children, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, GeoJSON, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import Forecast from './components/Forecast'
import WhatIf from './components/WhatIf'

import { API } from './api'
const POLL_MS = 3000 // live refresh; a tick is skipped while the previous one is still loading (/dispatch-plan ~2.5 s)

// API status words → chip tone + label. Stock: green/amber/red; routes: open/degraded/closed.
const TONE = { green: 'ok', amber: 'warn', red: 'crit', open: 'ok', degraded: 'warn', closed: 'crit' }
const RANK = { green: 0, amber: 1, red: 2 }
const label = (s) => s[0].toUpperCase() + s.slice(1)
// marker size doubles as a non-colour cue; the legend swatches use the same diameters (index.css .key)
const RADIUS = { green: 8, amber: 10, red: 12 }
const THEATRES = ['Ladakh', 'Arunachal', 'Punjab', 'All']

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

const same = (a, b) => a && b && a.postId === b.postId && a.itemId === b.itemId

// Selectable board row: click or Enter/Space; inner buttons stop propagation themselves.
function Row({ grid, selected, onSelect, children }) {
  return (
    <div
      className={`row${selected ? ' selected' : ''}`}
      style={{ '--grid': grid }}
      tabIndex={0}
      role="row"
      aria-selected={selected}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault()
          onSelect()
        }
      }}
    >
      {Children.toArray(children).map((c, i) => (
        <span key={i} role="gridcell" className="cell">
          {c}
        </span>
      ))}
    </div>
  )
}

const days = (d) => (d == null ? '—' : `${d.toFixed(1)} d`)
const etaDays = (iso) => Math.max(0, (new Date(iso) - Date.now()) / 864e5)
const NEXT = { proposed: ['approved', 'Approve'], approved: ['dispatched', 'Dispatch'] }
const GRID_STOCK = '2.5rem minmax(0, 1fr) 4.75rem 4rem'
const GRID_PLAN = '4rem minmax(0, 1fr) 4.5rem 4rem 5.25rem'

function Panel({ title, className = '', role, children }) {
  return (
    <section className={`panel ${className}`}>
      <h2>{title}</h2>
      <div className="panel-body" role={role} aria-label={role ? title : undefined}>{children}</div>
    </section>
  )
}

// Departures-board grammar shared by Alerts, Dispatch and Stock risk: header row + hairline rows.
// `grid` is the column template shared by header and rows; column `num` is the right-aligned time column.
function Board({ title, cols, grid, num, empty, children }) {
  return (
    <Panel title={title} role="grid">
      <div className="board-head" style={{ '--grid': grid }} role="row">
        {cols.map((c, i) => (
          <span key={c || i} role="columnheader" className={i === num ? 'num' : undefined}>
            {c}
          </span>
        ))}
      </div>
      {children?.length ? children : <p className="empty">{empty}</p>}
    </Panel>
  )
}

export default function App() {
  const [health, setHealth] = useState('Checking API…')
  const [places, setPlaces] = useState([])
  const [routes, setRoutes] = useState([])
  const [stock, setStock] = useState([])
  const [alerts, setAlerts] = useState([])
  const [plan, setPlan] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [selection, setSelection] = useState(null) // { postId, itemId }
  const [theatre, setTheatre] = useState('Ladakh')
  const [borders, setBorders] = useState(null)
  const [updated, setUpdated] = useState(null) // time of the last successful /stock load
  const [active, setActive] = useState([]) // what-if scenarios applied on top of the baseline
  const [wiOpen, setWiOpen] = useState(false)
  const [wiResult, setWiResult] = useState(null) // { kind: 'run' | 'reset', diff } of the last what-if call
  const [wiBusy, setWiBusy] = useState(false)
  const [wiError, setWiError] = useState(null)
  const wiTrigger = useRef(null)
  const busy = useRef(false)
  const points = useMemo(
    () => places.filter((p) => theatre === 'All' || p.region === theatre).map((p) => p.latlng),
    [places, theatre],
  )
  const regionOf = useMemo(() => Object.fromEntries(places.map((p) => [p.id, p.region])), [places])
  const worst = useMemo(() => worstByPost(stock), [stock])
  const stockRows = useMemo(
    () =>
      stock
        .filter((r) => r.kind === 'post')
        .sort((a, b) => RANK[b.status] - RANK[a.status] || a.days_of_supply - b.days_of_supply),
    [stock],
  )
  const dos = useMemo(() => Object.fromEntries(stock.map((r) => [`${r.location_id}/${r.item_id}`, r.days_of_supply])), [stock])
  const selPlan = selection && plan.find((p) => p.destination === selection.postId && p.item_id === selection.itemId)
  const selRow = selection && stock.find((r) => r.location_id === selection.postId && r.item_id === selection.itemId)
  const selEdges = selPlan?.edges ?? []
  const select = (postId, itemId) => {
    const next = same(selection, { postId, itemId }) ? null : { postId, itemId }
    setSelection(next)
    if (next && regionOf[postId]) setTheatre(regionOf[postId]) // jump to the post's theatre; deselecting keeps the user's choice
  }

  // the four live feeds, polled every POLL_MS
  const load = useCallback(() => {
    const get = (path, then) =>
      fetch(`${API}${path}`)
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(then)
    return Promise.allSettled([
      get('/routes', (d) =>
        setRoutes(d.features.map((f) => ({ ...f.properties, line: f.geometry.coordinates.map(([lng, lat]) => [lat, lng]) }))),
      ),
      get('/stock', (d) => (setStock(d.stock), setUpdated(new Date()))),
      get('/alerts', (d) => setAlerts(d.alerts)),
      get('/dispatch-plan', (d) => setPlan(d.plan)),
      get('/whatif', (d) => setActive(d.active)),
    ])
  }, [])

  useEffect(() => {
    const tick = () => {
      if (busy.current) return
      busy.current = true
      load().finally(() => (busy.current = false))
    }
    const t = setInterval(tick, POLL_MS)
    return () => clearInterval(t)
  }, [load])

  // what-if calls: surface the API's message, refresh every feed straight away, keep the diff for the sheet
  const whatif = (path, kind, body) => {
    if (wiBusy) return Promise.resolve()
    setWiBusy(true)
    setWiError(null)
    return fetch(`${API}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body && JSON.stringify(body) })
      .then(async (r) => {
        const d = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'That scenario was rejected. Check the values.')
        return d
      })
      .then((d) => (setWiResult({ kind, diff: d.diff }), load()))
      .catch((e) => (setWiError(e.message), setWiOpen(true))) // errors show in the sheet, wherever the call came from
      .finally(() => setWiBusy(false))
  }
  const runWhatIf = (body) => whatif('/whatif', 'run', body)
  const resetWhatIf = () => whatif('/whatif/reset', 'reset').then(() => setWiOpen(true))

  const advance = (row) => {
    fetch(`${API}/dispatch-plan/${row.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: NEXT[row.status][0] }),
    })
      .then(load)
      .catch(() => {})
  }

  useEffect(() => {
    document.querySelectorAll('.row.selected').forEach((el) => el.scrollIntoView({ block: 'nearest' }))
  }, [selection])

  useEffect(() => {
    load()
    fetch(`${import.meta.env.BASE_URL}boundaries.geojson`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setBorders)
      .catch((e) => console.warn('map borders unavailable:', e.message))
    fetch(`${API}/forecast/metrics`).then((r) => r.json()).then(setMetrics).catch(() => {})
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
            troops: f.properties.troop_strength,
            latlng: [f.geometry.coordinates[1], f.geometry.coordinates[0]],
          })),
        ),
      )
      .catch(() => {})
  }, [load])

  return (
    <div className="app">
      <header className="topbar">
        <h1>Forward Logistics Command</h1>
        <div className="topbar-end">
        <button ref={wiTrigger} type="button" className="btn" aria-expanded={wiOpen} onClick={() => setWiOpen((o) => !o)}>
          What-if
        </button>
        {active.length > 0 && (
          <button type="button" className="pill scenario" disabled={wiBusy} onClick={resetWhatIf} title={active.map((s) => s.label).join(', ')}>
            Scenario active ({active.length}) · Reset
          </button>
        )}
        <span className="pill" role="status">
          {health}
          {/* keyed on the load time: the dot remounts and replays its pulse on every refresh */}
          {updated && <span key={+updated} className="live-dot" aria-hidden="true" />}
          {updated && ` updated ${updated.toLocaleTimeString([], { hour12: false })}`}
        </span>
        </div>
      </header>
      <main className="board">
        <section className="panel map-panel">
          <div className="map-head">
            <h2>Network map</h2>
            <div className="seg" role="group" aria-label="Theatre">
              {THEATRES.map((t) => (
                <button key={t} type="button" className={`btn${t === theatre ? ' primary' : ''}`} aria-pressed={t === theatre} onClick={() => setTheatre(t)}>
                  {t}
                </button>
              ))}
            </div>
          </div>
          {/* fallback view until /locations arrives: northern India (Ladakh / Arunachal span) */}
          <MapContainer center={[31, 85]} zoom={5} zoomSnap={0.25} zoomControl={false}>
            <TileLayer
              attribution="Tiles &copy; Esri"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
            />
            {/* place names; borders are drawn from /boundaries.geojson below (Natural Earth, not authoritative, see README) */}
            <TileLayer
              zIndex={2}
              url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
            />
            {/* clipped Natural Earth lines: national solid dark, state thinner; keyed on kind via className */}
            {borders && (
              <GeoJSON
                data={borders}
                interactive={false}
                style={(f) => ({ className: `border ${f.properties.kind}`, fill: false })}
              />
            )}
            <FitBounds points={points} />
            {/* status lives in the class (colour + dash in index.css); keyed on status because Leaflet sets className only once */}
            {/* selection halo under the chosen alert's route; blue = selection */}
            {routes
              .filter((r) => selEdges.includes(r.id))
              .map((r) => (
                <Polyline key={`sel-${r.id}`} positions={r.line} interactive={false} pathOptions={{ className: 'route-sel' }} />
              ))}
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
                  {/* theatre view: every post is named; in All only at-risk posts are, with the status word */}
                  <Tooltip
                    key={theatre}
                    permanent={theatre !== 'All' || (!!w && w.status !== 'green')}
                    direction="right"
                    offset={[12, 0]}
                    className="map-label"
                  >
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
            grid={GRID_STOCK}
            num={3}
            empty="No stock-risk alerts. Posts with low supply appear here."
          >
            {alerts.map((a) => (
              <Row
                key={a.id}
                grid={GRID_STOCK}
                selected={same(selection, { postId: a.location_id, itemId: a.item_id })}
                onSelect={() => select(a.location_id, a.item_id)}
              >
                <span>{a.location_name.replace('Post ', 'P')}</span>
                <span>
                  {a.item_name}
                  {same(selection, { postId: a.location_id, itemId: a.item_id }) && <small className="sub">{a.message}</small>}
                </span>
                <Chip status={a.level} />
                <span className="time">{days(dos[`${a.location_id}/${a.item_id}`])}</span>
              </Row>
            ))}
          </Board>
          <Board
            title="Dispatch plan"
            cols={['Post', 'Item', 'Vehicle', 'ETA', '']}
            grid={GRID_PLAN}
            num={3}
            empty="No convoys recommended. Approved departures appear here."
          >
            {plan.map((p) => (
              <Row
                key={p.id}
                grid={GRID_PLAN}
                selected={same(selection, { postId: p.destination, itemId: p.item_id })}
                onSelect={() => select(p.destination, p.item_id)}
              >
                <span>{p.destination_name.replace('Post ', 'P')}</span>
                <span>
                  {p.item_name}
                  <small className="sub">
                    {p.qty} {p.unit} · {p.vehicle_id ? label(p.status) : 'Unassigned'}
                  </small>
                  {same(selection, { postId: p.destination, itemId: p.item_id }) && <small className="sub">{p.explanation}</small>}
                </span>
                <span>{p.vehicle_id ?? 'No truck'}</span>
                <span className="time">{p.eta ? days(etaDays(p.eta)) : '—'}</span>
                {NEXT[p.status] && p.vehicle_id ? (
                  <button
                    className="btn primary"
                    onClick={(e) => {
                      e.stopPropagation()
                      advance(p)
                    }}
                  >
                    {NEXT[p.status][1]}
                  </button>
                ) : (
                  <span className="num">{p.status === 'dispatched' ? 'Dispatched' : ''}</span>
                )}
              </Row>
            ))}
          </Board>
        </div>
        <div className="bottom">
          <Panel title="Forecast">
            <Forecast
              selection={selection}
              row={selRow}
              convoys={selection ? plan.filter((p) => p.destination === selection.postId) : []}
              metrics={metrics}
              Chip={Chip}
              days={days}
              etaDays={etaDays}
            />
          </Panel>
          <Board
            title="Stock risk"
            cols={['Post', 'Item', 'Status', 'Days left']}
            grid={GRID_STOCK}
            num={3}
            empty="Days of supply per post and item appear here."
          >
            {stockRows.map((r) => (
              <Row
                key={`${r.location_id}/${r.item_id}`}
                grid={GRID_STOCK}
                selected={same(selection, { postId: r.location_id, itemId: r.item_id })}
                onSelect={() => select(r.location_id, r.item_id)}
              >
                <span>{r.location_name.replace('Post ', 'P')}</span>
                <span>
                  {r.item_name}
                </span>
                <Chip status={r.status} />
                <span className="time">{days(r.days_of_supply)}</span>
              </Row>
            ))}
          </Board>
        </div>
      </main>
      <WhatIf
        open={wiOpen}
        onClose={() => setWiOpen(false)}
        triggerRef={wiTrigger}
        routes={routes}
        posts={places.filter((p) => p.kind === 'post')}
        active={active}
        result={wiResult}
        run={runWhatIf}
        reset={resetWhatIf}
        busy={wiBusy}
        error={wiError}
        Chip={Chip}
      />
    </div>
  )
}
