import { useState } from 'react'
import type { NmrPeak, NmrSpectrum } from '../types'

const W = 640
const PAD = { l: 44, r: 12, t: 12, b: 32 }

type Highlight = (atoms: number[] | null) => void

function ticks(lo: number, hi: number, n: number): number[] {
  const raw = (hi - lo) / n
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const out = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6))
  return out
}

function decimals(span: number): number {
  return span < 0.05 ? 3 : span < 0.5 ? 2 : span < 5 ? 1 : 0
}

// ---------------------------------------------------------------- simulated multiplet

const LINE_WIDTH_HZ = 1.0
const BROAD_WIDTH_HZ = 25

/** One 1H signal as the spectrometer would show it at the chosen field, from the full spin simulation. */
export function Zoom({ data, peak }: { data: NmrSpectrum; peak: NmrPeak }) {
  const sim = data.simulation
  const [field, setField] = useState(400)
  if (!sim) return null
  const lines = sim.lines[String(field)] ?? []
  const spanHz = (peak.couplings ?? []).reduce((s, c) => s + c.J * c.n, 0) / 2 + (peak.exchangeable ? 60 : 15)
  const half = spanHz / field
  const lo = peak.shift - half
  const hi = peak.shift + half
  const broad = peak.exchangeable ? sim.broad.filter(([p]) => Math.abs(p - peak.shift) < 1e-3) : []
  const sharp = peak.exchangeable ? [] : lines.filter(([p]) => p > lo - half && p < hi + half)
  const n = 500
  const xs = Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1))
  const lorentz = (x: number, x0: number, fwhmHz: number) => {
    const g = fwhmHz / 2 / field
    return (g * g) / ((x - x0) ** 2 + g * g)
  }
  const ys = xs.map((x) => sharp.reduce((s, [p, w]) => s + w * lorentz(x, p, LINE_WIDTH_HZ), 0)
    + broad.reduce((s, [p, w]) => s + w * lorentz(x, p, BROAD_WIDTH_HZ), 0))
  // Scale to the chosen signal itself; taller neighbours that drift into view are clipped.
  const own = ((peak.couplings ?? []).reduce((s, c) => s + c.J * c.n, 0) / 2 + 3) / field
  const top = Math.max(...ys.filter((_, i) => Math.abs(xs[i] - peak.shift) <= own), 1e-9)
  const HZ = 180
  const pw = W - PAD.l - PAD.r
  const ph = HZ - PAD.t - PAD.b
  const sx = (x: number) => PAD.l + ((hi - x) / (hi - lo)) * pw
  const sy = (y: number) => PAD.t + ph - (Math.min(y, top * 1.15) / top) * (ph - 6)
  const path = xs.map((x, i) => `${i ? 'L' : 'M'}${sx(x).toFixed(1)},${sy(ys[i]).toFixed(1)}`).join('')
  const d = decimals(hi - lo)
  return (
    <div className="nmr-zoom">
      <div className="toolbar small">
        <span className="muted">Spectrometer</span>
        {sim.fields.map((f) => (
          <button key={f} type="button" className={f === field ? 'active' : ''} onClick={() => setField(f)}>{f} MHz</button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${HZ}`} role="img" aria-label={`Simulated signal at ${field} MHz`}>
        <g className="axis">
          <line x1={PAD.l} x2={PAD.l + pw} y1={PAD.t + ph} y2={PAD.t + ph} />
          {ticks(lo, hi, 6).map((t) => (
            <g key={t}>
              <line x1={sx(t)} x2={sx(t)} y1={PAD.t + ph} y2={PAD.t + ph + 4} />
              <text x={sx(t)} y={PAD.t + ph + 15} textAnchor="middle">{t.toFixed(d)}</text>
            </g>
          ))}
          <text x={PAD.l + pw} y={PAD.t + ph + 27} textAnchor="end" className="unit">δ / ppm ({(2 * spanHz).toFixed(0)} Hz wide)</text>
        </g>
        <path d={path} className="curve sim" />
      </svg>
      <p className="muted small">
        δ {peak.shift.toFixed(2)} at {field} MHz, simulated from every coupling, not just the n+1 rule: at low field, coupled
        signals that are close in shift lean towards each other (roofing) and can grow extra lines.
        {!sim.exact && ` Groups of more than ${10} coupled protons are drawn first order.`}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------- 2D

type Experiment = 'cosy' | 'hsqc' | 'hmbc'
const EXPERIMENTS: { id: Experiment; label: string; about: string }[] = [
  { id: 'cosy', label: 'COSY', about: 'protons coupled to each other, on neighbouring carbons (H-C-C-H)' },
  { id: 'hsqc', label: 'HSQC', about: 'each carbon and the protons on it' },
  { id: 'hmbc', label: 'HMBC', about: 'carbons two or three bonds from a proton, which links fragments across quaternary carbons and heteroatoms' },
]

export function TwoD({ data, onHighlight }: { data: NmrSpectrum; onHighlight: Highlight }) {
  const [exp, setExp] = useState<Experiment>('cosy')
  const [sel, setSel] = useState<number | null>(null)
  const hp = data.h.peaks
  const cp = data.c.peaks
  const corr = data.correlations
  if (!corr || hp.length === 0) return <p className="muted">No protons to correlate.</p>
  const isCosy = exp === 'cosy'
  const points: { x: number; y: number; atoms: number[]; diag?: boolean; text: string }[] = []
  if (isCosy) {
    hp.forEach((p) => points.push({ x: p.shift, y: p.shift, atoms: p.atoms, diag: true, text: `δH ${p.shift.toFixed(2)} (${p.label})` }))
    for (const [a, b] of corr.cosy) {
      const text = `δH ${hp[a].shift.toFixed(2)} (${hp[a].label}) and δH ${hp[b].shift.toFixed(2)} (${hp[b].label})`
      const atoms = [...hp[a].atoms, ...hp[b].atoms]
      points.push({ x: hp[a].shift, y: hp[b].shift, atoms, text }, { x: hp[b].shift, y: hp[a].shift, atoms, text })
    }
  } else {
    for (const [c, h] of corr[exp]) {
      points.push({ x: hp[h].shift, y: cp[c].shift, atoms: [...hp[h].atoms, ...cp[c].atoms],
        text: `δH ${hp[h].shift.toFixed(2)} (${hp[h].label}) and δC ${cp[c].shift.toFixed(1)} (${cp[c].label})` })
    }
  }
  const hs = hp.map((p) => p.shift)
  const ys = isCosy ? hs : cp.map((p) => p.shift)
  const pad = (v: number[], m: number, floor: number, ceil: number) =>
    [Math.max(floor, Math.min(...v) - m), Math.min(ceil, Math.max(...v) + m)] as const
  const [x0, x1] = pad(hs, 0.5, -0.5, 14)
  const [y0, y1] = isCosy ? [x0, x1] : pad(ys, 10, -5, 230)
  const HH = 340
  const pw = W - PAD.l - PAD.r
  const ph = HH - PAD.t - PAD.b
  const sx = (v: number) => PAD.l + ((x1 - v) / (x1 - x0)) * pw
  const sy = (v: number) => PAD.t + ((v - y0) / (y1 - y0)) * ph
  const pick = (i: number | null) => {
    setSel(i)
    onHighlight(i === null ? null : points[i].atoms)
  }
  const about = EXPERIMENTS.find((e) => e.id === exp)!
  return (
    <div className="spectrum">
      <div className="toolbar small">
        {EXPERIMENTS.map((e) => (
          <button key={e.id} type="button" className={exp === e.id ? 'active' : ''} onClick={() => { setExp(e.id); pick(null) }}>{e.label}</button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${HH}`} role="img" aria-label={`${about.label} map`}>
        <g className="axis">
          <line x1={PAD.l} x2={PAD.l + pw} y1={PAD.t + ph} y2={PAD.t + ph} />
          <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={PAD.t + ph} />
          {ticks(x0, x1, 7).map((t) => (
            <g key={`x${t}`}>
              <line x1={sx(t)} x2={sx(t)} y1={PAD.t + ph} y2={PAD.t + ph + 4} />
              <text x={sx(t)} y={PAD.t + ph + 15} textAnchor="middle">{t}</text>
            </g>
          ))}
          {ticks(y0, y1, 6).map((t) => (
            <g key={`y${t}`}>
              <line x1={PAD.l - 4} x2={PAD.l} y1={sy(t)} y2={sy(t)} />
              <line x1={PAD.l} x2={PAD.l + pw} y1={sy(t)} y2={sy(t)} className="grid" />
              <text x={PAD.l - 6} y={sy(t) + 3} textAnchor="end">{t}</text>
            </g>
          ))}
          <text x={PAD.l + pw} y={PAD.t + ph + 27} textAnchor="end" className="unit">δH / ppm</text>
          <text x={4} y={PAD.t + 8} className="unit">{isCosy ? 'δH' : 'δC'}</text>
        </g>
        {isCosy && <line x1={sx(x0)} y1={sy(x0)} x2={sx(x1)} y2={sy(x1)} className="diagonal" />}
        {points.map((p, i) => (
          <circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={p.diag ? 4 : 6} className={`xpeak${p.diag ? ' diag' : ''}${sel === i ? ' sel' : ''}`}
            onMouseEnter={() => pick(i)} onMouseLeave={() => pick(null)} />
        ))}
      </svg>
      <p className="small">{sel !== null ? points[sel].text : <span className="muted">Point at a cross peak to see which signals it joins.</span>}</p>
      <p className="muted small">
        {about.label} shows {about.about}. {points.filter((p) => !p.diag).length / (isCosy ? 2 : 1)} cross peak{points.length === 1 ? '' : 's'},
        worked out from the structure and the predicted shifts above.
      </p>
    </div>
  )
}
