import { useEffect, useState } from 'react'
import { api, describeFailure } from '../api'
import type { AdminStats, AuthState } from '../types'

function Bars({ title, data }: { title: string; data: { day: string; count: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.count))
  return (
    <section className="card">
      <header className="card-head"><h2>{title}</h2><span className="muted small">{data.reduce((s, d) => s + d.count, 0)} in period</span></header>
      {data.length === 0 ? <p className="muted">Nothing yet.</p> : (
        <div className="bars">
          {data.map((d) => (
            <div key={d.day} className="bar" title={`${d.day}: ${d.count}`}>
              <div className="bar-fill" style={{ height: `${(100 * d.count) / max}%` }} />
              <span className="bar-label">{d.day.slice(5)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export function StatsPanel({ auth, onOpen }: { auth: AuthState; onOpen: (name: string) => void }) {
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [days, setDays] = useState(14)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.adminStats(auth, days).then(setStats).catch((e) => setError(describeFailure(e)))
  }, [auth, days])

  if (error) return <p className="error">{error}</p>
  if (!stats) return <p className="muted">Loading...</p>
  const t = stats.totals
  const tiles: [string, number][] = [
    ['Molecules cached', t.molecules_cached],
    ['Names cached', t.names_cached],
    ['Cache hits', t.cache_hits],
    ['Users', t.users],
    ['Quiz attempts', t.quiz_attempts],
    ['Quiz correct', t.quiz_correct],
    ['Assignments', t.assignments],
    ['Assignment completions', t.assignment_completions],
  ]
  return (
    <div className="stats">
      <div className="toolbar">
        <span className="muted">Period</span>
        {[7, 14, 30, 90].map((d) => <button key={d} type="button" className={days === d ? 'active' : ''} onClick={() => setDays(d)}>{d} days</button>)}
      </div>
      <div className="stat-tiles">
        {tiles.map(([label, v]) => (
          <div key={label} className="card stat-tile"><span className="stat-value">{v}</span><span className="muted small">{label}</span></div>
        ))}
      </div>
      <div className="grid2">
        <Bars title="New molecules per day" data={stats.new_molecules_per_day} />
        <Bars title="Quiz attempts per day" data={stats.quiz_attempts_per_day} />
      </div>
      <div className="grid2">
        <section className="card">
          <header className="card-head"><h2>Most viewed molecules</h2></header>
          <ul className="list">
            {stats.top_molecules.map((m) => (
              <li key={m.smiles}>
                <button type="button" className="list-btn" onClick={() => onOpen(m.name || m.smiles)}>
                  <span className="list-title">{m.name || m.smiles}</span>
                  <span className="list-sub">{m.hits} views · {m.smiles}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="card">
          <header className="card-head"><h2>Inputs that failed most</h2><span className="muted small">no user data stored</span></header>
          {stats.top_failures.length === 0 ? <p className="muted">None recorded.</p> : (
            <ul className="list">
              {stats.top_failures.map((f) => (
                <li key={f.text} className="fail-row">
                  <span className="list-title">{f.text} <span className="muted small">×{f.count}</span></span>
                  <span className="list-sub">{f.reason}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}
