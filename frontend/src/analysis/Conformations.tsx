import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ChairOut, Molecule, NewmanOut, ProjectionInfo } from '../types'
import { analysisApi } from './api'
import type { ChairEnergy, TorsionScan } from './types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

const W = 420
const H = 220
const PAD = { l: 42, r: 12, t: 12, b: 30 }

function Plot({ scan, selected, onSelect }: { scan: TorsionScan; selected: number; onSelect: (a: number) => void }) {
  const ymax = Math.max(scan.barrier, 0.5)
  const x = (a: number) => PAD.l + (a / 360) * (W - PAD.l - PAD.r)
  const y = (e: number) => H - PAD.b - (e / ymax) * (H - PAD.t - PAD.b)
  const pts = [...scan.points, { angle: 360, energy: scan.points[0].energy }]
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.angle).toFixed(1)},${y(p.energy).toFixed(1)}`).join(' ')
  const ticks = [0, 60, 120, 180, 240, 300, 360]
  const yticks = Array.from({ length: 5 }, (_, i) => (ymax * i) / 4)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="scan-plot" role="img" aria-label="Energy against dihedral angle">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={PAD.t} y2={H - PAD.b} stroke="var(--border)" strokeDasharray={t % 120 === 0 ? '' : '3 3'} />
          <text x={x(t)} y={H - PAD.b + 16} textAnchor="middle" fontSize="10" fill="var(--muted)">{t}°</text>
        </g>
      ))}
      {yticks.map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="var(--border)" />
          <text x={PAD.l - 4} y={y(v) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{v.toFixed(1)}</text>
        </g>
      ))}
      <text x={W / 2} y={H - 2} textAnchor="middle" fontSize="10" fill="var(--muted)">dihedral {scan.labels[0]} / {scan.labels[1]}</text>
      <text transform={`translate(10 ${H / 2}) rotate(-90)`} textAnchor="middle" fontSize="10" fill="var(--muted)">kcal/mol</text>
      <path d={path} fill="none" stroke="var(--accent)" strokeWidth="2" />
      <line x1={x(scan.start_dihedral)} x2={x(scan.start_dihedral)} y1={PAD.t} y2={H - PAD.b} stroke="#f59e0b" strokeWidth="1.5" />
      {scan.points.map((p) => (
        <circle key={p.angle} cx={x(p.angle)} cy={y(p.energy)} r={p.angle === selected ? 5 : 3} fill={p.angle === selected ? '#dc2626' : 'var(--accent)'} style={{ cursor: 'pointer' }} onClick={() => onSelect(p.angle)}>
          <title>{p.angle}°: {p.energy.toFixed(2)} kcal/mol</title>
        </circle>
      ))}
    </svg>
  )
}

export function Conformations({ mol, onHighlight }: Props) {
  const [info, setInfo] = useState<ProjectionInfo | null>(null)
  const [tab, setTab] = useState<'scan' | 'chair'>('scan')
  const [bond, setBond] = useState(0)
  const [scan, setScan] = useState<TorsionScan | null>(null)
  const [scanErr, setScanErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState<number | null>(null)
  const [newman, setNewman] = useState<NewmanOut | null>(null)
  const [ring, setRing] = useState(0)
  const [chair, setChair] = useState<ChairEnergy | null>(null)
  const [chairSvg, setChairSvg] = useState<ChairOut | null>(null)
  const [chairErr, setChairErr] = useState<string | null>(null)

  useEffect(() => {
    setInfo(null)
    setScan(null)
    setChair(null)
    setChairSvg(null)
    setSel(null)
    setNewman(null)
    setBond(0)
    setRing(0)
    setScanErr(null)
    setChairErr(null)
    api.projections(mol.smiles).then((i) => {
      setInfo(i)
      setTab(i.newman_bonds.length ? 'scan' : 'chair')
    }).catch(() => setInfo({ newman_bonds: [], chair_rings: [] }))
  }, [mol.smiles])

  const runScan = () => {
    if (!info?.newman_bonds[bond]) return
    const [f, b] = info.newman_bonds[bond].atoms
    setBusy(true)
    setScanErr(null)
    analysisApi.scan(mol.smiles, f, b).then((s) => {
      setScan(s)
      setSel(null)
      setNewman(null)
      onHighlight(s.atoms, '#f59e0b')
    }).catch((e) => setScanErr(e instanceof Error ? e.message : 'Scan failed')).finally(() => setBusy(false))
  }

  useEffect(() => {
    if (!scan || sel === null || !info) return
    const [f, b] = info.newman_bonds[bond].atoms
    const rotate = ((sel - scan.start_dihedral) % 360 + 360) % 360
    api.newman(mol.smiles, f, b, rotate).then(setNewman).catch(() => setNewman(null))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel, scan])

  const runChair = () => {
    if (!info?.chair_rings[ring]) return
    setBusy(true)
    setChairErr(null)
    const r = info.chair_rings[ring]
    Promise.all([analysisApi.chairEnergy(mol.smiles, r), api.chair(mol.smiles, r)])
      .then(([e, s]) => {
        setChair(e)
        setChairSvg(s)
        onHighlight(r, '#f59e0b')
      })
      .catch((e) => setChairErr(e instanceof Error ? e.message : 'Could not compare the chairs'))
      .finally(() => setBusy(false))
  }

  if (!info || (info.newman_bonds.length === 0 && info.chair_rings.length === 0)) return null
  const selPoint = scan && sel !== null ? scan.points.find((p) => p.angle === sel) : null
  const kind = (a: number) => (a % 120 === 0 ? 'eclipsed' : a % 60 === 0 ? 'staggered' : '')

  return (
    <section className="card">
      <header className="card-head">
        <h2>Conformational energy</h2>
        <div className="toolbar">
          {info.newman_bonds.length > 0 && <button type="button" className={tab === 'scan' ? 'active' : ''} onClick={() => setTab('scan')}>Bond rotation</button>}
          {info.chair_rings.length > 0 && <button type="button" className={tab === 'chair' ? 'active' : ''} onClick={() => setTab('chair')}>Chair flip</button>}
        </div>
      </header>

      {tab === 'scan' && (
        <div className="bonding-body">
          <div className="toolbar">
            <label className="check">
              Bond
              <select value={bond} onChange={(e) => { setBond(Number(e.target.value)); setScan(null) }} aria-label="Bond to rotate">
                {info.newman_bonds.map((b, i) => <option key={b.label} value={i}>{b.label}</option>)}
              </select>
            </label>
            <button type="button" className="primary" onClick={runScan} disabled={busy}>{busy ? 'Scanning...' : scan ? 'Scan again' : 'Scan 0 to 360°'}</button>
            {scan && <span className="muted small">barrier {scan.barrier.toFixed(1)} kcal/mol</span>}
          </div>
          {scanErr && <p className="error small">{scanErr}</p>}
          {scan && (
            <div className="bonding-split">
              <div>
                <Plot scan={scan} selected={sel ?? -1} onSelect={setSel} />
                <p className="muted small">Select a point to see that conformer as a Newman projection. The orange line marks the dihedral in the 3D model. Minima at {scan.minima.join('°, ')}°; maxima at {scan.maxima.join('°, ')}°.</p>
              </div>
              <div>
                {newman && selPoint ? (
                  <>
                    <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: newman.svg }} />
                    <p className="small">{selPoint.angle}° {kind(selPoint.angle)}: {selPoint.energy.toFixed(2)} kcal/mol above the minimum</p>
                  </>
                ) : (
                  <p className="muted small">No conformer selected.</p>
                )}
                <p className="muted small">{scan.note}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'chair' && (
        <div className="bonding-body">
          <div className="toolbar">
            {info.chair_rings.length > 1 && (
              <label className="check">
                Ring
                <select value={ring} onChange={(e) => { setRing(Number(e.target.value)); setChair(null) }} aria-label="Ring">
                  {info.chair_rings.map((r, i) => <option key={r.join('-')} value={i}>ring {i + 1}</option>)}
                </select>
              </label>
            )}
            <button type="button" className="primary" onClick={runChair} disabled={busy}>{busy ? 'Comparing...' : 'Compare the two chairs'}</button>
          </div>
          {chairErr && <p className="error small">{chairErr}</p>}
          {chair && chairSvg && (
            <>
              <p><b>{chair.summary}</b></p>
              <div className="bonding-split">
                {chair.chairs.map((c) => (
                  <div key={c.which} className="chair-box">
                    <div className="ring-head">
                      <b>{c.which === 'current' ? 'Chair shown in 3D' : 'Flipped chair'}</b>
                      <span className={`tag ${c.energy === 0 ? 'tag-ok' : 'tag-warn'}`}>{c.energy === 0 ? 'lower' : `+${c.energy.toFixed(1)} kcal/mol`}</span>
                    </div>
                    <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: c.which === 'current' ? chairSvg.svg : chairSvg.svg_flipped }} />
                    <p className="small">
                      axial: {c.axial.length ? c.axial.map((a) => a.label).join(', ') : 'none'}; equatorial: {c.equatorial.length ? c.equatorial.map((a) => a.label).join(', ') : 'none'}
                    </p>
                  </div>
                ))}
              </div>
              <p className="muted small">{chair.note}</p>
            </>
          )}
        </div>
      )}
    </section>
  )
}
