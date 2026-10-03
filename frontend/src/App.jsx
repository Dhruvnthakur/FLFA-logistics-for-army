import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const API = import.meta.env.VITE_API_URL

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
  const points = useMemo(() => places.map((p) => p.latlng), [places])

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
            latlng: [f.geometry.coordinates[1], f.geometry.coordinates[0]],
          })),
        ),
      )
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
            {places.map((p) => (
              <CircleMarker key={p.id} center={p.latlng} radius={6} pathOptions={{ color: '#1d1d1f', weight: 2, fillColor: '#fff', fillOpacity: 1 }}>
                <Tooltip>{p.name}</Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
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
