import { useEffect, useState } from 'react'
import { api } from '../api'
import type { IrSpectrum, Molecule, MsNode, MsSpectrum, NmrSpectrum } from '../types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null) => void
}

type Tab = 'h' | 'c' | 'ir' | 'ms'

const W = 640
const H = 260
const PAD = { l: 36, r: 12, t: 14, b: 30 }
const PW = W - PAD.l - PAD.r
const PH = H - PAD.t - PAD.b

export function Spectra({ mol, onHighlight }: Props) {
  const [tab, setTab] = useState<Tab>('h')
  const [nmr, setNmr] = useState<NmrSpectrum | null>(null)
  const [ir, setIr] = useState<IrSpectrum | null>(null)
  const [ms, setMs] = useState<MsSpectrum | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setNmr(null)
    setIr(null)
    setMs(null)
    setError(null)
  }, [mol.smiles])

  useEffect(() => {
    const need = tab === 'ir' ? !ir : tab === 'ms' ? !ms : !nmr
    if (!need) return
    let live = true
    setLoading(true)
    setError(null)
    const kind = tab === 'ir' ? 'ir' : tab === 'ms' ? 'ms' : 'nmr'
    api.spectra(mol.smiles, kind)
      .then((d) => {
        if (!live) return
        if (kind === 'ir') setIr(d as IrSpectrum)
        else if (kind === 'ms') setMs(d as MsSpectrum)
        else setNmr(d as NmrSpectrum)
      })
      .catch((e: Error) => live && setError(e.message))
      .finally(() => live && setLoading(false))
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, mol.smiles, nmr, ir, ms])

  return (
    <section className="card spectra">
      <header className="card-head">
        <h2>Spectra</h2>
        <div className="toolbar">
          {(['h', 'c', 'ir', 'ms'] as Tab[]).map((t) => (
            <button key={t} type="button" className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
              {t === 'h' ? '¹H NMR' : t === 'c' ? '¹³C NMR' : t === 'ir' ? 'IR' : 'Mass spec'}
            </button>
          ))}
        </div>
      </header>
      {error && <p className="warn">{error}</p>}
      {loading && <p className="muted small">Loading…</p>}
      {!loading && (tab === 'h' || tab === 'c') && nmr && <Nmr data={nmr} nucleus={tab} onHighlight={onHighlight} />}
      {!loading && tab === 'ir' && ir && <Ir data={ir} onHighlight={onHighlight} />}
      {!loading && tab === 'ms' && ms && <Ms data={ms} onHighlight={onHighlight} />}
    </section>
  )
}

// ---------------------------------------------------------------- helpers

function Axis({ x0, x1, ticks, unit, reversed }: { x0: number; x1: number; ticks: number[]; unit: string; reversed?: boolean }) {
  const sx = (v: number) => PAD.l + ((reversed ? x1 - v : v - x0) / (x1 - x0)) * PW
  return (
    <g className="axis">
      <line x1={PAD.l} x2={PAD.l + PW} y1={PAD.t + PH} y2={PAD.t + PH} />
      {ticks.map((t) => (
        <g key={t}>
          <line x1={sx(t)} x2={sx(t)} y1={PAD.t + PH} y2={PAD.t + PH + 4} />
          <text x={sx(t)} y={PAD.t + PH + 15} textAnchor="middle">{t}</text>
        </g>
      ))}
      <text x={PAD.l + PW} y={PAD.t + PH + 26} textAnchor="end" className="unit">{unit}</text>
    </g>
  )
}

function range(a: number, b: number, step: number): number[] {
  const out = []
  for (let v = a; step > 0 ? v <= b : v >= b; v += step) out.push(v)
  return out
}

// ---------------------------------------------------------------- NMR

function Nmr({ data, nucleus, onHighlight }: { data: NmrSpectrum; nucleus: 'h' | 'c'; onHighlight: Props['onHighlight'] }) {
  const peaks = data[nucleus].peaks
  const [sel, setSel] = useState<number | null>(null)
  const max = nucleus === 'h' ? 12 : 220
  const sx = (ppm: number) => PAD.l + ((max - Math.min(Math.max(ppm, 0), max)) / max) * PW
  const top = Math.max(...peaks.map((p) => p.integration), 1)
  // Skip integration labels that would overlap a neighbour's (peaks are sorted by shift).
  const labelled = peaks.map((p, i) => (i === 0 || Math.abs(peaks[i - 1].shift - p.shift) > max / 40) && (i === peaks.length - 1 || Math.abs(peaks[i + 1].shift - p.shift) > max / 40))
  const hover = (i: number | null) => {
    setSel(i)
    onHighlight(i === null ? null : peaks[i].atoms)
  }
  return (
    <div className="spectrum">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${nucleus === 'h' ? '1H' : '13C'} NMR`}>
        <Axis x0={0} x1={max} ticks={nucleus === 'h' ? range(0, 12, 1) : range(0, 220, 20)} unit="δ / ppm" reversed />
        {peaks.map((p, i) => {
          const h = (p.integration / top) * (PH - 24)
          const x = sx(p.shift)
          return (
            <g key={i} className={`peak ${sel === i ? 'sel' : ''}`} onMouseEnter={() => hover(i)} onMouseLeave={() => hover(null)} onClick={() => hover(sel === i ? null : i)}>
              <rect x={x - 6} y={PAD.t} width={12} height={PH} className="hit" />
              <Multiplet x={x} y0={PAD.t + PH} h={h} mult={nucleus === 'h' ? p.multiplicity ?? 's' : 's'} couplings={nucleus === 'h' ? p.couplings : undefined} />
              {nucleus === 'h' && (labelled[i] || sel === i) && <text x={x} y={PAD.t + PH - h - 6} textAnchor="middle" className="int">{p.integration}H</text>}
            </g>
          )
        })}
      </svg>
      <table className="peak-table">
        <thead><tr><th>δ (ppm)</th><th>{nucleus === 'h' ? 'H' : 'C'}</th>{nucleus === 'h' && <th>mult.</th>}<th>environment</th></tr></thead>
        <tbody>
          {peaks.map((p, i) => (
            <tr key={i} className={sel === i ? 'sel' : ''} onMouseEnter={() => hover(i)} onMouseLeave={() => hover(null)}>
              <td>{p.shift.toFixed(nucleus === 'h' ? 2 : 1)}</td>
              <td>{p.integration}</td>
              {nucleus === 'h' && <td>{p.multiplicity}{p.exchangeable ? ' (br, exchangeable)' : ''}{p.couplings && p.couplings.length > 0 && <span className="muted">, J = {p.couplings.map((c) => c.J.toFixed(1)).join(', ')} Hz</span>}</td>}
              <td>{p.label}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{peaks.length} signal{peaks.length === 1 ? '' : 's'}. {data.note}{nucleus === 'h' && ' Multiplicities from first-order coupling: 7 Hz across freely rotating bonds, Karplus dihedrals in rings, 16/10.5 Hz trans/cis on alkenes, 8/2 Hz ortho/meta. Splittings in the drawing are exaggerated for visibility.'}</p>
    </div>
  )
}

function Multiplet({ x, y0, h, mult, couplings }: { x: number; y0: number; h: number; mult: string; couplings?: { J: number; n: number }[] }) {
  // Lines from the actual couplings (each J splits every line n times),
  // exaggerated to ~0.6 px per Hz so a 7 Hz triplet is visible; falls back
  // to binomial spacing when no couplings are known, a jagged blob for m.
  let lines: { off: number; rel: number }[]
  if (couplings && couplings.length > 0 && mult !== 'm') {
    lines = [{ off: 0, rel: 1 }]
    for (const c of couplings) {
      for (let k = 0; k < c.n; k++) {
        const next = new Map<number, number>()
        for (const l of lines) {
          for (const d of [-c.J / 2, c.J / 2]) {
            const key = Math.round((l.off + d) * 10)
            next.set(key, (next.get(key) ?? 0) + l.rel / 2)
          }
        }
        lines = [...next.entries()].map(([k, rel]) => ({ off: k / 10, rel })).sort((a, b) => a.off - b.off)
      }
    }
    const top = Math.max(...lines.map((l) => l.rel))
    lines = lines.map((l) => ({ off: l.off * 0.6, rel: l.rel / top }))
  } else {
    const n = { s: 1, d: 2, t: 3, q: 4, quint: 5, sext: 6, sept: 7 }[mult as 's']
    let rel: number[]
    if (n) {
      rel = [1]
      for (let i = 1; i < n; i++) rel.push((rel[i - 1] * (n - i)) / i)
      const top = Math.max(...rel)
      rel = rel.map((v) => v / top)
    } else {
      rel = [0.5, 0.9, 0.7, 1, 0.6]
    }
    lines = rel.map((r, i) => ({ off: (i - (rel.length - 1) / 2) * 3, rel: r }))
  }
  return (
    <g className="stick">
      {lines.map((l, i) => <line key={i} x1={x + l.off} x2={x + l.off} y1={y0} y2={y0 - h * l.rel} />)}
    </g>
  )
}

// ---------------------------------------------------------------- IR

function Ir({ data, onHighlight }: { data: IrSpectrum; onHighlight: Props['onHighlight'] }) {
  const [showPred, setShowPred] = useState(true)
  const [showExp, setShowExp] = useState(true)
  const [sel, setSel] = useState<number | null>(null)
  const sx = (cm: number) => PAD.l + ((4000 - Math.min(Math.max(cm, 400), 4000)) / 3600) * PW
  const sy = (t: number) => PAD.t + (1 - Math.min(Math.max(t, 0), 1)) * PH
  const hover = (i: number | null) => {
    setSel(i)
    onHighlight(i === null ? null : data.predicted[i].atoms)
  }
  // Synthetic transmittance curve: one Gaussian dip per predicted band.
  const depth = { strong: 0.8, medium: 0.5, weak: 0.25 } as Record<string, number>
  const xs = range(4000, 400, -8)
  const pred = xs.map((x) => {
    let t = 1
    for (const b of data.predicted) {
      const sigma = b.shape === 'very broad' ? 220 : b.shape === 'broad' ? 90 : 18
      t -= depth[b.intensity] * Math.exp(-((x - b.centre) ** 2) / (2 * sigma * sigma))
    }
    return Math.max(t, 0.02)
  })
  const path = (X: number[], Y: number[]) => X.map((x, i) => `${i ? 'L' : 'M'}${sx(x).toFixed(1)},${sy(Y[i]).toFixed(1)}`).join(' ')
  const exp = data.experimental
  return (
    <div className="spectrum">
      <div className="toolbar">
        <label className="check"><input type="checkbox" checked={showPred} onChange={(e) => setShowPred(e.target.checked)} /> predicted bands</label>
        {exp && <label className="check"><input type="checkbox" checked={showExp} onChange={(e) => setShowExp(e.target.checked)} /> experimental (NIST{exp.state ? `, ${exp.state}` : ''})</label>}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="IR spectrum">
        <Axis x0={400} x1={4000} ticks={range(4000, 500, -500)} unit="wavenumber / cm⁻¹" reversed />
        <text x={PAD.l - 4} y={PAD.t + 8} textAnchor="end" className="unit">%T</text>
        {showPred && data.predicted.map((b, i) => (
          <rect key={i} x={sx(b.high)} y={PAD.t} width={Math.max(sx(b.low) - sx(b.high), 2)} height={PH} className={`band ${sel === i ? 'sel' : ''}`} onMouseEnter={() => hover(i)} onMouseLeave={() => hover(null)} />
        ))}
        {showPred && <path d={path(xs, pred)} className="curve pred" />}
        {showExp && exp && <path d={path(exp.x, exp.y)} className="curve exp" />}
      </svg>
      <table className="peak-table">
        <thead><tr><th>cm⁻¹</th><th>band</th><th>intensity</th></tr></thead>
        <tbody>
          {data.predicted.map((b, i) => (
            <tr key={i} className={sel === i ? 'sel' : ''} onMouseEnter={() => hover(i)} onMouseLeave={() => hover(null)}>
              <td>{b.low}–{b.high}</td><td>{b.name}</td><td>{b.intensity}{b.shape !== 'sharp' ? `, ${b.shape}` : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        {data.note}{' '}
        {exp && <a href={exp.url} target="_blank" rel="noreferrer">View at NIST</a>}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------- MS

function Ms({ data, onHighlight }: { data: MsSpectrum; onHighlight: Props['onHighlight'] }) {
  const [sel, setSel] = useState<number | null>(null)
  const exp = data.experimental
  const tree = data.tree ?? []
  const ions = tree.filter((n) => n.parent >= 0)
  const maxMz = Math.ceil((Math.max(data.nominal_mass, ...(exp ? exp.peaks.map((p) => p.mz) : [])) + 12) / 10) * 10
  const sx = (mz: number) => PAD.l + (mz / maxMz) * PW
  const sy = (rel: number) => PAD.t + (1 - rel / 100) * PH
  const hover = (id: number | null) => {
    setSel(id)
    const node = id === null ? null : tree.find((n) => n.id === id)
    onHighlight(node && node.atoms.length ? node.atoms : null)
  }
  // Depth-first order for the table, so each ion sits under its precursor.
  const rows: { node: MsNode; depth: number }[] = []
  const walk = (parent: number, depth: number) => {
    for (const n of tree.filter((n) => n.parent === parent)) {
      rows.push({ node: n, depth })
      walk(n.id, depth + 1)
    }
  }
  walk(-1, 0)
  const height = (n: MsNode) => (n.parent === 0 ? Math.max(15, 70 - ions.indexOf(n) * 6) : 12)
  const tickStep = maxMz > 300 ? 50 : maxMz > 120 ? 20 : 10
  return (
    <div className="spectrum">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Mass spectrum">
        <Axis x0={0} x1={maxMz} ticks={range(0, maxMz, tickStep)} unit="m/z" />
        {exp && exp.peaks.map((p, i) => <line key={`e${i}`} x1={sx(p.mz)} x2={sx(p.mz)} y1={sy(0)} y2={sy(p.rel)} className="stick exp" />)}
        {data.isotopes.map((p, i) => (
          <g key={`i${i}`} className="peak mol-ion" onMouseEnter={() => onHighlight(null)}>
            <line x1={sx(p.nominal)} x2={sx(p.nominal)} y1={sy(0)} y2={sy(p.rel)} className="stick pred" />
            {i === 0 && <text x={sx(p.nominal)} y={sy(p.rel) - 4} textAnchor="middle" className="int">M⁺• {p.nominal}</text>}
          </g>
        ))}
        {ions.map((f) => (
          <g key={`f${f.id}`} className={`peak ${sel === f.id ? 'sel' : ''}`} onMouseEnter={() => hover(f.id)} onMouseLeave={() => hover(null)} onClick={() => hover(sel === f.id ? null : f.id)}>
            <rect x={sx(f.nominal) - 5} y={PAD.t} width={10} height={PH} className="hit" />
            <line x1={sx(f.nominal)} x2={sx(f.nominal)} y1={sy(0)} y2={sy(height(f))} className="stick frag" />
            {f.isotopes.slice(1).map((iso) => <line key={iso.nominal} x1={sx(iso.nominal)} x2={sx(iso.nominal)} y1={sy(0)} y2={sy((height(f) * iso.rel) / 100)} className="stick frag" />)}
            <text x={sx(f.nominal)} y={sy(height(f)) - 4} textAnchor="middle" className="int">{f.nominal}</text>
          </g>
        ))}
      </svg>
      <p className="small">
        <b>{data.formula}</b>, exact mass {data.exact_mass}, M⁺• at m/z {data.nominal_mass}
        {data.isotopes.length > 1 && <> · isotope pattern {data.isotopes.map((p) => `${p.nominal} (${Math.round(p.rel)}%)`).join(', ')}</>}
      </p>
      <table className="peak-table ms-tree">
        <thead><tr><th>m/z</th><th>ion</th><th>from</th><th>loss</th><th>why</th></tr></thead>
        <tbody>
          {rows.map(({ node: f, depth }) => (
            <tr key={f.id} className={sel === f.id ? 'sel' : ''} onMouseEnter={() => hover(f.id)} onMouseLeave={() => hover(null)}>
              <td>{f.nominal}{f.isotopes.length > 1 && <span className="muted small"> / {f.isotopes.slice(1).map((i) => `${i.nominal} (${Math.round(i.rel)}%)`).join(', ')}</span>}</td>
              <td>
                <div className="ms-ion" style={{ paddingLeft: `${depth * 1.1}rem` }}>
                  {depth > 0 && <span className="ms-branch" aria-hidden="true">└</span>}
                  <span>{f.formula}</span>
                  {f.svg && <span className="ms-thumb" dangerouslySetInnerHTML={{ __html: f.svg }} />}
                </div>
              </td>
              <td>{f.parent < 0 ? '' : f.parent === 0 ? 'M⁺•' : `m/z ${tree.find((n) => n.id === f.parent)?.nominal}`}</td>
              <td>{f.loss ? `−${f.loss}` : ''}</td>
              <td>{f.why}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">
        Fragment heights are illustrative (ranked by expected stability), not intensities. Ions are grouped under the ion they come from. {data.note}{' '}
        {exp && <a href={exp.url} target="_blank" rel="noreferrer">View at NIST</a>}
      </p>
    </div>
  )
}
