import { useEffect, useMemo, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { API } from '../api'
const short = (iso) => iso.slice(5)

// Forecast + post view for the selected post × item: the one-sentence explanation, stock facts,
// actual-vs-predicted demand, accuracy badge and the convoys inbound to that post.
export default function Forecast({ selection, row, convoys, metrics, Chip, days, etaDays }) {
  const [fc, setFc] = useState(null)
  const [err, setErr] = useState(null) // key whose fetch failed
  const key = selection && `${selection.postId}/${selection.itemId}`
  const qty = row?.quantity

  useEffect(() => {
    if (!key) return
    let live = true
    fetch(`${API}/forecast/${key}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => live && (setErr(null), setFc(d)))
      .catch(() => live && setErr(key))
    return () => { live = false }
  }, [key, qty]) // stock changes move days-of-supply, so refetch with it

  const data = useMemo(
    () => fc && [
      ...(fc.history ?? []).map((p) => ({ d: short(p.date), actual: p.qty })),
      ...(fc.forecast ?? []).map((p) => ({ d: short(p.date), predicted: p.qty })),
    ],
    [fc],
  )
  const m = metrics?.per_item?.[selection?.itemId]

  if (!selection) return <p className="empty">Select an alert or stock row to see its forecast and post view.</p>
  if (err === key) return <p className="empty">Forecast unavailable for this post and item.</p>
  if (!fc || !row || `${fc.post_id}/${fc.item_id}` !== key) return <p className="empty">Loading forecast…</p>
  return (
    <div className="fc">
      <div>
        <div className="fc-title">
          <span><strong>{row.location_name} · {row.item_name}</strong> <Chip status={row.status} /></span>
          <span className="fc-key"><span className="ln" /> Actual <span className="ln dash" /> Predicted</span>
        </div>
        <p className="fc-why">{fc.explanation}</p>
      </div>
      <div className="fc-head">
        <dl className="fc-facts">
          <div><dt>Stock</dt><dd>{Math.round(row.quantity).toLocaleString()} {row.unit}</dd></div>
          <div><dt>Days left</dt><dd>{days(row.days_of_supply)}</dd></div>
          <div><dt>Lead time</dt><dd>{days(row.lead_time_days)}</dd></div>
        </dl>
        {m && (
          <span className="badge" title={`Held-out ${metrics.holdout_days} days, ${metrics.horizon_days}-day horizon`}>
            MAE {m.model.mae.toPrecision(3)} · MAPE {m.model.mape}% <small>vs naive {m.baseline.mape}%</small>
          </span>
        )}
      </div>
      <div className="fc-chart" role="img" aria-label={`Daily ${row.item_name} demand in ${fc.unit}: actual last ${fc.history?.length ?? 0} days, then predicted next ${fc.forecast?.length ?? 0} days`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="d" tick={{ fontSize: 12, fill: 'var(--ink-3)' }} interval="preserveStartEnd" minTickGap={24} />
            <YAxis width={40} tick={{ fontSize: 12, fill: 'var(--ink-3)' }} />
            <Tooltip formatter={(v, n) => [`${v} ${fc.unit}/day`, n]} />
            <Line dataKey="actual" name="Actual" stroke="var(--ink-3)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line dataKey="predicted" name="Predicted" stroke="var(--ink)" strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {convoys.length ? (
        <ul className="fc-convoys" aria-label="Inbound convoys">
          {convoys.slice(0, 2).map((p) => (
            <li key={p.id}>
              {p.vehicle_id ?? 'No truck'} · {p.item_name} {p.qty} {p.unit} · {p.vehicle_id ? `${p.status}, ETA ${days(etaDays(p.eta))}` : 'unassigned'}
            </li>
          ))}
          {convoys.length > 2 && <li>+{convoys.length - 2} more in the dispatch plan</li>}
        </ul>
      ) : (
        <p className="fc-none">No inbound convoys planned.</p>
      )}
    </div>
  )
}
