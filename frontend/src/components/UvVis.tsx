import { useState } from 'react'
import type { UvSpectrum } from '../types'

const W = 640
const H = 200
const PAD = { l: 36, r: 12, t: 12, b: 30 }
const LO = 190
const HI = 520

/** Woodward-Fieser estimate: the absorption band drawn at the estimated maximum and the increments it adds up from. */
export function UvVis({ data, onHighlight }: { data: UvSpectrum; onHighlight: (atoms: number[] | null) => void }) {
  const [sel, setSel] = useState<number | null>(null)
  const pick = (i: number | null) => {
    setSel(i)
    onHighlight(i === null ? null : i < 0 ? data.chromophore : data.parts[i].atoms)
  }
  if (data.lambda_max === null) return <p className="muted">{data.note}</p>
  const pw = W - PAD.l - PAD.r
  const ph = H - PAD.t - PAD.b
  const sx = (nm: number) => PAD.l + ((nm - LO) / (HI - LO)) * pw
  const lam = data.lambda_max
  const xs = Array.from({ length: 331 }, (_, i) => LO + i)
  const path = xs.map((x, i) => {
    const y = Math.exp(-((x - lam) ** 2) / (2 * 18 * 18))
    return `${i ? 'L' : 'M'}${sx(x).toFixed(1)},${(PAD.t + ph - y * (ph - 8)).toFixed(1)}`
  }).join('')
  return (
    <div className="spectrum">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Estimated UV-Vis absorption">
        <defs>
          <linearGradient id="visible" x1="0" x2="1">
            <stop offset="0%" stopColor="#7c3aed" /><stop offset="20%" stopColor="#2563eb" /><stop offset="40%" stopColor="#16a34a" />
            <stop offset="60%" stopColor="#eab308" /><stop offset="80%" stopColor="#f97316" /><stop offset="100%" stopColor="#dc2626" />
          </linearGradient>
        </defs>
        <rect x={sx(400)} y={PAD.t + ph + 1} width={sx(HI) - sx(400)} height={4} fill="url(#visible)" />
        <g className="axis">
          <line x1={PAD.l} x2={PAD.l + pw} y1={PAD.t + ph} y2={PAD.t + ph} />
          {[200, 250, 300, 350, 400, 450, 500].map((t) => (
            <g key={t}>
              <line x1={sx(t)} x2={sx(t)} y1={PAD.t + ph} y2={PAD.t + ph + 4} />
              <text x={sx(t)} y={PAD.t + ph + 16} textAnchor="middle">{t}</text>
            </g>
          ))}
          <text x={PAD.l + pw} y={PAD.t + ph + 27} textAnchor="end" className="unit">λ / nm</text>
        </g>
        <path d={path} className="curve uv" onMouseEnter={() => pick(-1)} onMouseLeave={() => pick(null)} />
        <line x1={sx(lam)} x2={sx(lam)} y1={PAD.t} y2={PAD.t + ph} className="uv-max" />
        <text x={sx(lam) + 4} y={PAD.t + 10} className="int">λmax ≈ {lam} nm</text>
      </svg>
      <table className="peak-table">
        <thead><tr><th>{data.rule === 'polyene' ? 'Fieser-Kuhn term' : 'Woodward-Fieser increment'}</th><th>nm</th></tr></thead>
        <tbody>
          {data.parts.map((p, i) => (
            <tr key={i} className={sel === i ? 'sel' : ''} onMouseEnter={() => pick(i)} onMouseLeave={() => pick(null)}>
              <td>{p.label}</td><td>{p.nm > 0 && i > 0 ? `+${p.nm}` : p.nm}</td>
            </tr>
          ))}
          <tr><td><b>λmax</b></td><td><b>{lam}</b></td></tr>
        </tbody>
      </table>
      <p className="muted small">{data.note} Point at a row to see the atoms it counts.</p>
    </div>
  )
}
