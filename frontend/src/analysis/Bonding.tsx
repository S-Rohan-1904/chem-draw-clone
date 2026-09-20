import { Fragment, useEffect, useRef, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { Bonding as BondingData, Dipole } from './types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

type Tab = 'chirality' | 'shapes' | 'rings' | 'dbe' | 'oxidation' | 'polarity' | 'hbond'

const TABS: { id: Tab; label: string }[] = [
  { id: 'chirality', label: 'Chirality' },
  { id: 'shapes', label: 'Shapes' },
  { id: 'rings', label: 'Aromaticity' },
  { id: 'dbe', label: 'Unsaturation' },
  { id: 'oxidation', label: 'Oxidation states' },
  { id: 'polarity', label: 'Polarity' },
  { id: 'hbond', label: 'H-bonding' },
]

interface Viewer3d {
  addArrow: (spec: Record<string, unknown>) => unknown
  removeShape: (s: unknown) => void
  render: () => void
}

function useDipoleArrow(dipole: Dipole | null | undefined, show: boolean) {
  const shape = useRef<unknown>(null)
  useEffect(() => {
    const v = (window as unknown as { viewer3d?: Viewer3d }).viewer3d
    if (!v) return
    if (shape.current) {
      v.removeShape(shape.current)
      shape.current = null
    }
    if (show && dipole && dipole.debye > 0.05) {
      const [mx, my, mz] = dipole.vector
      const n = Math.hypot(mx, my, mz) || 1
      const len = Math.min(4, Math.max(1.5, 1 + dipole.debye * 0.6))
      const [cx, cy, cz] = dipole.centre
      const u = [mx / n, my / n, mz / n]
      // Chemistry convention: the arrow points to the negative end.
      shape.current = v.addArrow({
        start: { x: cx + (u[0] * len) / 2, y: cy + (u[1] * len) / 2, z: cz + (u[2] * len) / 2 },
        end: { x: cx - (u[0] * len) / 2, y: cy - (u[1] * len) / 2, z: cz - (u[2] * len) / 2 },
        radius: 0.12,
        radiusRatio: 2.5,
        mid: 0.7,
        color: '#7c3aed',
      })
    }
    v.render()
    return () => {
      if (shape.current) {
        v.removeShape(shape.current)
        shape.current = null
        v.render()
      }
    }
  }, [dipole, show])
}

export function Bonding({ mol, onHighlight }: Props) {
  const [data, setData] = useState<BondingData | null>(null)
  const [tab, setTab] = useState<Tab>('chirality')
  const [showDipole, setShowDipole] = useState(false)
  const [detail, setDetail] = useState<number | null>(null)

  useEffect(() => {
    setData(null)
    setShowDipole(false)
    setDetail(null)
    analysisApi.bonding(mol.smiles).then(setData).catch(() => setData(null))
  }, [mol.smiles])

  useDipoleArrow(data?.polarity.dipole, showDipole && tab === 'polarity')

  if (!data) return null
  const sym = (i: number) => `${mol.atoms?.[i]?.symbol ?? ''}${i + 1}`
  const chir = data.chirality
  const u = data.unsaturation

  return (
    <section className="card bonding">
      <header className="card-head">
        <h2>Structure and bonding</h2>
        <div className="toolbar">
          {TABS.map((t) => (
            <button key={t.id} type="button" className={tab === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>{t.label}</button>
          ))}
        </div>
      </header>

      {tab === 'chirality' && (
        <div className="bonding-body">
          <p className="bonding-title">
            <span className={`tag chir-${chir.kind}`}>{chir.title}</span>
          </p>
          <p>{chir.reason}</p>
          {chir.centres.length > 0 && (
            <div className="chips">
              {chir.centres.map((i) => (
                <button key={i} type="button" className="chip" onMouseEnter={() => onHighlight([i], '#2563eb')} onMouseLeave={() => onHighlight(null)}>{sym(i)}</button>
              ))}
              {chir.pairs.map(([a, b]) => (
                <button key={`${a}-${b}`} type="button" className="chip" onMouseEnter={() => onHighlight([a, b], '#7c3aed')} onMouseLeave={() => onHighlight(null)}>mirror pair {sym(a)} / {sym(b)}</button>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'shapes' && (
        <div className="bonding-body">
          {data.vsepr.length === 0 && <p className="muted">No atom with two or more neighbours.</p>}
          {data.vsepr.length > 0 && (
            <table className="bonding-table">
              <thead>
                <tr><th>Atom</th><th>Electron domains</th><th>Lone pairs</th><th>Shape</th><th>Ideal angle</th><th>In the 3D model</th></tr>
              </thead>
              <tbody>
                {data.vsepr.map((v) => (
                  <tr key={v.idx} onMouseEnter={() => onHighlight([v.idx], '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
                    <td>{sym(v.idx)}</td>
                    <td>{v.domains}</td>
                    <td>{v.lone_pairs}{v.note ? <span className="muted small"> ({v.note})</span> : null}</td>
                    <td>{v.shape}</td>
                    <td>{v.ideal_angle !== null ? `${v.ideal_angle}°` : ''}</td>
                    <td>{v.model_angle !== null ? `${v.model_angle}°` : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="muted small">VSEPR: electron domains around an atom spread out as far as possible. Lone pairs take more room, so angles close up a little.</p>
        </div>
      )}

      {tab === 'rings' && (
        <div className="bonding-body">
          {data.rings.length === 0 && <p className="muted">No rings.</p>}
          {data.rings.map((r, k) => (
            <div key={k} className="ring-row" onMouseEnter={() => onHighlight(r.atoms, r.aromatic ? '#7c3aed' : '#94a3b8')} onMouseLeave={() => onHighlight(null)}>
              <div className="ring-head">
                <b>{r.size}-membered ring</b>
                <span className={`tag ${r.aromatic ? 'tag-ok' : ''}`}>{r.aromatic ? 'aromatic' : 'not aromatic'}</span>
                <span className="muted small">{r.pi_electrons} π electrons</span>
              </div>
              <p>{r.verdict}</p>
              <p className="muted small">{r.details.join(' · ')}</p>
            </div>
          ))}
          <p className="muted small">Hückel's rule: a planar, fully conjugated ring with 4n+2 π electrons is aromatic.</p>
        </div>
      )}

      {tab === 'dbe' && (
        <div className="bonding-body">
          <p className="bonding-title">Degrees of unsaturation: <b>{u.dbe}</b></p>
          <p>From the formula ({u.formula_terms}): <code>{u.from_formula}</code></p>
          <p>From the structure: {u.breakdown} = {u.structural}</p>
          {!u.consistent && <p className="muted small">The two counts differ because the formula count only handles C, H, N, O and halogens.</p>}
          {u.note && <p className="muted small">{u.note}</p>}
        </div>
      )}

      {tab === 'oxidation' && (
        <div className="bonding-body bonding-split">
          <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: data.oxidation.svg }} />
          <div>
            <div className="chips">
              {data.oxidation.atoms.map((a) => (
                <button
                  key={a.idx}
                  type="button"
                  className={`chip ${detail === a.idx ? 'active' : ''}`}
                  onClick={() => setDetail(detail === a.idx ? null : a.idx)}
                  onMouseEnter={() => onHighlight([a.idx], '#f59e0b')}
                  onMouseLeave={() => onHighlight(null)}
                >
                  {a.symbol}{a.idx + 1}: {a.oxidation_state > 0 ? '+' : ''}{a.oxidation_state}
                </button>
              ))}
            </div>
            {detail !== null && data.oxidation.atoms[detail] && (
              <p className="small">
                {sym(detail)}: {data.oxidation.atoms[detail].terms.length ? data.oxidation.atoms[detail].terms.join(', ') : 'no bonds to other elements'}
              </p>
            )}
            <p className="muted small">Each bond's electrons are assigned to the more electronegative atom; bonds between identical atoms are split evenly.</p>
          </div>
        </div>
      )}

      {tab === 'polarity' && (
        <div className="bonding-body bonding-split">
          <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: data.polarity.svg }} />
          <div>
            <dl className="props">
              {data.polarity.bonds.map((b) => (
                <Fragment key={b.bond_idx}>
                  <dt onMouseEnter={() => onHighlight(b.atoms, b.class === 'nonpolar' ? '#94a3b8' : '#f59e0b')} onMouseLeave={() => onHighlight(null)}>{b.label}</dt>
                  <dd>ΔEN {b.delta_en.toFixed(2)}, <span className={`pol-${b.class}`}>{b.class}</span>{b.negative_end !== null ? `, δ- on ${sym(b.negative_end)}` : ''}</dd>
                </Fragment>
              ))}
              {data.polarity.ch && (
                <>
                  <dt>C-H</dt>
                  <dd>ΔEN {data.polarity.ch.delta_en.toFixed(2)}, nonpolar</dd>
                </>
              )}
            </dl>
            {data.polarity.dipole && (
              <div className="dipole-row">
                <span>Dipole moment estimate: <b>{data.polarity.dipole.debye.toFixed(2)} D</b></span>
                {data.polarity.dipole.debye > 0.05 && (
                  <button type="button" className={showDipole ? 'active' : ''} onClick={() => setShowDipole((s) => !s)}>{showDipole ? 'Hide arrow in 3D' : 'Show arrow in 3D'}</button>
                )}
              </div>
            )}
            <p className="muted small">Polar: ΔEN 0.4 to 1.7, ionic above 1.7. The dipole comes from Gasteiger partial charges on the 3D model and points to the negative end.</p>
          </div>
        </div>
      )}

      {tab === 'hbond' && (
        <div className="bonding-body bonding-split">
          <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: data.hbond.svg }} />
          <div>
            <p>
              <span className="swatch-inline" style={{ background: '#2563eb' }} /> donors: {data.hbond.donors.length ? data.hbond.donors.map(sym).join(', ') : 'none'}
              <br />
              <span className="swatch-inline" style={{ background: '#dc2626' }} /> acceptors: {data.hbond.acceptors.length ? data.hbond.acceptors.map(sym).join(', ') : 'none'}
              {data.hbond.both.length > 0 && (
                <>
                  <br />
                  <span className="swatch-inline" style={{ background: '#7c3aed' }} /> both: {data.hbond.both.map(sym).join(', ')}
                </>
              )}
            </p>
            <p className="bonding-title">Water solubility: <b>{data.solubility.class}</b></p>
            <p>{data.solubility.text}. Estimated log S = {data.solubility.logs} (about {formatSol(data.solubility.g_per_l)}).</p>
            <ul className="bonding-list">
              {data.solubility.reasons.map((r) => <li key={r}>{r}</li>)}
            </ul>
            <p className="muted small">{data.solubility.method}</p>
          </div>
        </div>
      )}
    </section>
  )
}

function formatSol(gPerL: number): string {
  if (gPerL >= 1000) return 'over 1 kg per litre'
  if (gPerL >= 1) return `${gPerL.toFixed(gPerL >= 10 ? 0 : 1)} g per litre`
  if (gPerL >= 0.001) return `${(gPerL * 1000).toFixed(gPerL * 1000 >= 10 ? 0 : 1)} mg per litre`
  return `${(gPerL * 1e6).toFixed(1)} µg per litre`
}
