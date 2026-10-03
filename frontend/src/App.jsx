import { useEffect, useState } from 'react'
import { MapContainer, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const API = import.meta.env.VITE_API_URL

export default function App() {
  const [health, setHealth] = useState('checking…')

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then((d) => setHealth(d.status === 'ok' ? `API ok · PostGIS ${d.postgis}` : `API error: ${d.db}`))
      .catch(() => setHealth('API unreachable'))
  }, [])

  return (
    <div className="app">
      <header>
        <strong>Forward Logistics Command</strong>
        <span>{health}</span>
      </header>
      {/* centred on northern India (Ladakh / Arunachal span) */}
      <MapContainer center={[31, 85]} zoom={5} className="map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
      </MapContainer>
    </div>
  )
}
