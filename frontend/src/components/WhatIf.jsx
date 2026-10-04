import { useEffect, useRef, useState } from 'react'

const TYPES = [
  ['close_route', 'Close route'],
  ['storm', 'Storm'],
  ['troop_change', 'Troops'],
]
const STATUSES = ['closed', 'degraded', 'open']
const d1 = (v) => (v == null ? '—' : `${v.toFixed(1)} d`)

// One titled group of diff rows; nothing renders when the group is empty.
function Group({ title, items, children }) {
  if (!items.length) return null
  return (
    <section className="wi-group">
      <h3>{title}</h3>
      <ul>{items.map(children)}</ul>
    </section>
  )
}

function Diff({ result, Chip }) {
  const { diff } = result
  const none =
    !diff.new_red.length && !diff.worse.length && !diff.recovered.length && !diff.rerouted.length &&
    !diff.newly_unassigned.length && !diff.routes_changed.length
  return (
    <div className="wi-diff">
      <p className="wi-headline">{result.kind === 'reset' && none ? 'Baseline restored. Nothing else changed.' : diff.headline}</p>
      {none ? null : (
        <>
          <Group title="Routes" items={diff.routes_changed}>
            {(r) => (
              <li key={r.id}>
                <span>{r.name}</span>
                <span className="wi-flow">
                  <Chip status={r.before} /> <i aria-hidden="true">→</i> <Chip status={r.after} />
                </span>
              </li>
            )}
          </Group>
          <Group title="Turns Red" items={diff.new_red}>
            {(m) => <StockLine key={`${m.post_id}${m.item_id}`} m={m} Chip={Chip} />}
          </Group>
          <Group title="Getting worse" items={diff.worse}>
            {(m) => <StockLine key={`${m.post_id}${m.item_id}`} m={m} Chip={Chip} />}
          </Group>
          <Group title="Recovers" items={diff.recovered}>
            {(m) => <StockLine key={`${m.post_id}${m.item_id}`} m={m} Chip={Chip} />}
          </Group>
          <Group title="Rerouted convoys" items={diff.rerouted}>
            {(r) => (
              <li key={`${r.post_id}${r.item_id}`}>
                <span>
                  {r.post_name.replace('Post ', 'P')} {r.item_name}
                  <small className="sub">
                    {r.before_via} → {r.after_via}
                  </small>
                </span>
                <span className="wi-delta">{r.delta_days == null ? '—' : `${r.delta_days > 0 ? '+' : ''}${r.delta_days.toFixed(1)} d`}</span>
              </li>
            )}
          </Group>
          <Group title="No truck free" items={diff.newly_unassigned}>
            {(u, i) => (
              <li key={i}>
                <span>
                  {u.post_name.replace('Post ', 'P')} {u.item_name}
                </span>
                <span className="wi-delta">Unassigned</span>
              </li>
            )}
          </Group>
        </>
      )}
    </div>
  )
}

function StockLine({ m, Chip }) {
  return (
    <li>
      <span>
        {m.post_name.replace('Post ', 'P')} {m.item_name}
        <small className="sub">
          {d1(m.dos_after)} of supply · resupply {m.lead_before == null ? '—' : m.lead_before.toFixed(1)} →{' '}
          {m.lead_after == null ? 'none' : `${m.lead_after.toFixed(1)} d`}
        </small>
      </span>
      <Chip status={m.after} />
    </li>
  )
}

// What-if sheet (FR-23/24): a parallel tool, so no scrim — the map stays live behind it.
export default function WhatIf({ open, onClose, triggerRef, routes, posts, active, result, run, reset, busy, error, Chip }) {
  const [type, setType] = useState('storm')
  const [routeId, setRouteId] = useState('E9')
  const [status, setStatus] = useState('closed')
  const [radius, setRadius] = useState(15)
  const [postId, setPostId] = useState('P7')
  const [strength, setStrength] = useState(140)
  const sheet = useRef(null)
  const sortedRoutes = [...routes].sort((a, b) => a.id.slice(1) - b.id.slice(1))

  useEffect(() => {
    if (open) sheet.current?.querySelector('button')?.focus()
    else if (sheet.current?.contains(document.activeElement)) triggerRef.current?.focus()
  }, [open, triggerRef])

  useEffect(() => {
    if (!open) return
    const esc = (e) => e.key === 'Escape' && !e.defaultPrevented && !/SELECT|INPUT/.test(e.target.tagName) && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [open, onClose])

  // the selects show their first option when the remembered id isn't in the list yet; submit what is shown
  const rid = sortedRoutes.some((r) => r.id === routeId) ? routeId : sortedRoutes[0]?.id
  const pid = posts.some((p) => p.id === postId) ? postId : posts[0]?.id
  const post = posts.find((p) => p.id === pid)
  const body =
    type === 'close_route'
      ? { type, route_id: rid, status }
      : type === 'storm'
        ? { type, route_id: rid, radius_km: Number(radius) }
        : { type, post_id: pid, strength: Number(strength) }

  return (
    <aside ref={sheet} className={`sheet${open ? ' open' : ''}`} aria-label="What-if simulator" inert={!open}>
      <header className="sheet-head">
        <h2>What-if</h2>
        <button type="button" className="btn" onClick={onClose}>
          Close
        </button>
      </header>
      <div className="sheet-body">
        <div className="seg" role="group" aria-label="Scenario">
          {TYPES.map(([t, name]) => (
            <button key={t} type="button" className={`btn${t === type ? ' primary' : ''}`} aria-pressed={t === type} onClick={() => setType(t)}>
              {name}
            </button>
          ))}
        </div>

        <form
          className="wi-form"
          onSubmit={(e) => {
            e.preventDefault()
            run(body)
          }}
        >
          {type !== 'troop_change' && (
            <label>
              {type === 'storm' ? 'Storm over' : 'Route'}
              <select value={rid} onChange={(e) => setRouteId(e.target.value)}>
                {sortedRoutes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {type === 'close_route' && (
            <label>
              Set to
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s[0].toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {type === 'storm' && (
            <label>
              Radius (km)
              <input type="number" min="5" max="100" step="5" value={radius} onChange={(e) => setRadius(e.target.value)} />
              <small>Closes every road within this distance of the route’s far end.</small>
            </label>
          )}
          {type === 'troop_change' && (
            <>
              <label>
                Post
                <select value={pid} onChange={(e) => setPostId(e.target.value)}>
                  {posts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Troop strength
                <input type="number" min="1" max="1000" value={strength} onChange={(e) => setStrength(e.target.value)} />
                {post?.troops != null && <small>Currently {post.troops}. Demand scales with strength.</small>}
              </label>
            </>
          )}
          <div className="wi-actions">
            <button type="submit" className="btn primary" disabled={busy}>
              {busy ? 'Running…' : 'Run scenario'}
            </button>
            <button type="button" className="btn" disabled={busy || !active.length} onClick={reset}>
              Reset to baseline
            </button>
          </div>
          {error && (
            <p className="wi-error" role="alert">
              {error}
            </p>
          )}
        </form>

        {active.length > 0 && (
          <section className="wi-group">
            <h3>Active</h3>
            <ul>
              {active.map((s, i) => (
                <li key={i}>
                  <span>{s.label}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        <div aria-live="polite">{result && <Diff result={result} Chip={Chip} />}</div>
      </div>
    </aside>
  )
}
