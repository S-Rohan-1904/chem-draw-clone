import { useEffect, useRef, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { AcidBase as AcidBaseData } from './types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

const PRESETS = [
  { label: 'stomach 1.5', ph: 1.5 },
  { label: 'blood 7.4', ph: 7.4 },
  { label: 'intestine 8', ph: 8 },
]

export function AcidBase({ mol, onHighlight }: Props) {
  const [ph, setPh] = useState(7.4)
  const [data, setData] = useState<AcidBaseData | null>(null)
  const [empty, setEmpty] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    setData(null)
    setEmpty(false)
    setPh(7.4)
  }, [mol.smiles])

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => {
      analysisApi
        .acidBase(mol.smiles, ph)
        .then((r) => {
          setData(r)
          setEmpty(r.sites.length === 0)
        })
        .catch(() => setData(null))
    }, data ? 150 : 0)
    return () => {
      if (timer.current) window.clearTimeout(timer.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mol.smiles, ph])

  if (!data || empty) return null
  const sym = (i: number) => `${mol.atoms?.[i]?.symbol ?? ''}${i + 1}`
  const charge = data.species_charge

  return (
    <section className="card">
      <header className="card-head">
        <h2>Acids and bases</h2>
        <span className="muted small">{data.sites.length} ionisable site{data.sites.length !== 1 ? 's' : ''}</span>
      </header>
      <div className="bonding-split">
        <div>
          <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: data.species_svg }} />
          <p className="muted small">Dominant form at pH {ph.toFixed(1)}: <code>{data.species_smiles}</code>, charge {charge > 0 ? '+' : ''}{charge}</p>
        </div>
        <div>
          <label className="check slider ph-slider">
            pH
            <input type="range" min={0} max={14} step={0.1} value={ph} onChange={(e) => setPh(Number(e.target.value))} aria-label="pH" />
            <b>{ph.toFixed(1)}</b>
          </label>
          <div className="toolbar">
            {PRESETS.map((p) => (
              <button key={p.label} type="button" className={Math.abs(p.ph - ph) < 0.05 ? 'active' : ''} onClick={() => setPh(p.ph)}>{p.label}</button>
            ))}
            {data.pi !== null && <button type="button" className={Math.abs(data.pi - ph) < 0.05 ? 'active' : ''} onClick={() => setPh(data.pi as number)}>pI {data.pi.toFixed(1)}</button>}
          </div>
          <table className="bonding-table">
            <thead>
              <tr><th>Site</th><th>Group</th><th>pKa</th><th>Ionised at pH {ph.toFixed(1)}</th></tr>
            </thead>
            <tbody>
              {data.sites.map((s) => (
                <tr key={s.atom_idx} onMouseEnter={() => onHighlight(s.atoms, s.kind === 'acid' ? '#dc2626' : '#2563eb')} onMouseLeave={() => onHighlight(null)}>
                  <td>{sym(s.atom_idx)}</td>
                  <td>{s.group} <span className={`tag ${s.kind === 'acid' ? 'tag-acid' : 'tag-base'}`}>{s.kind}</span></td>
                  <td>{s.pka}{!s.in_water_range ? <span className="muted small"> (outside the water range)</span> : null}</td>
                  <td>
                    <span className="frac-bar" aria-hidden="true"><span style={{ width: `${Math.round(s.fraction_ionised * 100)}%`, background: s.kind === 'acid' ? '#dc2626' : '#2563eb' }} /></span>
                    {Math.round(s.fraction_ionised * 100)}% {s.kind === 'acid' ? 'deprotonated' : 'protonated'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>Average net charge at this pH: <b>{data.net_charge > 0 ? '+' : ''}{data.net_charge.toFixed(2)}</b>{data.pi !== null ? <span>, isoelectric point pI = <b>{data.pi.toFixed(2)}</b></span> : null}</p>
          <p className="muted small">{data.note}</p>
        </div>
      </div>
    </section>
  )
}
