import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const API = import.meta.env.VITE_API_URL

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

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then((d) => setHealth(d.status === 'ok' ? `API ok · PostGIS ${d.postgis}` : `API error: ${d.db}`))
      .catch(() => setHealth('API unreachable'))
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
          {/* centred on northern India (Ladakh / Arunachal span) */}
          <MapContainer center={[31, 85]} zoom={5} zoomControl={false}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
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
