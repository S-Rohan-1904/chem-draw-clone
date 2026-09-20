import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ChairOut, Molecule, NewmanOut, ProjectionInfo } from '../types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null) => void
}

export function Projections({ mol, onHighlight }: Props) {
  const [info, setInfo] = useState<ProjectionInfo | null>(null)
  const [bond, setBond] = useState(0)
  const [rotate, setRotate] = useState(0)
  const [newman, setNewman] = useState<NewmanOut | null>(null)
  const [ring, setRing] = useState(0)
  const [chair, setChair] = useState<ChairOut | null>(null)
  const [flipped, setFlipped] = useState(false)
  const [tab, setTab] = useState<'newman' | 'chair'>('newman')

  useEffect(() => {
    setInfo(null)
    setNewman(null)
    setChair(null)
    setBond(0)
    setRing(0)
    setRotate(0)
    api.projections(mol.smiles).then((i) => {
      setInfo(i)
      if (i.newman_bonds.length === 0 && i.chair_rings.length > 0) setTab('chair')
      else setTab('newman')
    }).catch(() => setInfo({ newman_bonds: [], chair_rings: [] }))
  }, [mol])

  useEffect(() => {
    if (!info || tab !== 'newman' || !info.newman_bonds[bond]) return
    const [f, b] = info.newman_bonds[bond].atoms
    api.newman(mol.smiles, f, b, rotate).then(setNewman).catch(() => setNewman(null))
    onHighlight([f, b])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info, bond, rotate, tab])

  useEffect(() => {
    if (!info || tab !== 'chair' || !info.chair_rings[ring]) return
    api.chair(mol.smiles, info.chair_rings[ring]).then(setChair).catch(() => setChair(null))
    onHighlight(info.chair_rings[ring])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [info, ring, tab])

  if (!info || (info.newman_bonds.length === 0 && info.chair_rings.length === 0)) return null

  return (
    <section className="card">
      <header className="card-head">
        <h2>Projections</h2>
        <div className="toolbar">
          {info.newman_bonds.length > 0 && <button type="button" className={tab === 'newman' ? 'active' : ''} onClick={() => setTab('newman')}>Newman</button>}
          {info.chair_rings.length > 0 && <button type="button" className={tab === 'chair' ? 'active' : ''} onClick={() => setTab('chair')}>Chair</button>}
        </div>
      </header>

      {tab === 'newman' && (
        <div className="projection">
          <div className="toolbar">
            <label className="check">
              Bond
              <select value={bond} onChange={(e) => setBond(Number(e.target.value))} aria-label="Bond">
                {info.newman_bonds.map((b, i) => <option key={b.label} value={i}>{b.label}</option>)}
              </select>
            </label>
            <label className="check slider">
              Rotate back carbon
              <input type="range" min={0} max={360} step={5} value={rotate} onChange={(e) => setRotate(Number(e.target.value))} aria-label="Rotate" />
              <span className="muted small">{rotate}°</span>
            </label>
            {newman?.dihedral !== null && newman?.dihedral !== undefined && (
              <span className="muted small">dihedral {newman.dihedral}° {Math.abs(((newman.dihedral % 120) + 120) % 120 - 60) < 10 ? '(staggered)' : ((newman.dihedral % 120) + 120) % 120 < 10 || ((newman.dihedral % 120) + 120) % 120 > 110 ? '(eclipsed)' : ''}</span>
            )}
          </div>
          {newman && <div className="svg-wrap projection-svg" dangerouslySetInnerHTML={{ __html: newman.svg }} />}
        </div>
      )}

      {tab === 'chair' && chair && (
        <div className="projection">
          <div className="toolbar">
            {info.chair_rings.length > 1 && (
              <label className="check">
                Ring
                <select value={ring} onChange={(e) => setRing(Number(e.target.value))} aria-label="Ring">
                  {info.chair_rings.map((r, i) => <option key={r.join('-')} value={i}>ring {i + 1}</option>)}
                </select>
              </label>
            )}
            <button type="button" className={flipped ? 'active' : ''} onClick={() => setFlipped((f) => !f)}>Ring flip</button>
            <span className="muted small">
              {flipped ? chair.equatorial_count : chair.axial_count} axial, {flipped ? chair.axial_count : chair.equatorial_count} equatorial
              {chair.substituents.length > 0 && (flipped ? chair.equatorial_count : chair.axial_count) > (flipped ? chair.axial_count : chair.equatorial_count) ? ' (less stable chair)' : ''}
            </span>
          </div>
          <div className="svg-wrap projection-svg" dangerouslySetInnerHTML={{ __html: flipped ? chair.svg_flipped : chair.svg }} />
          {chair.substituents.length === 0 && <p className="muted small">No substituents on this ring.</p>}
        </div>
      )}
    </section>
  )
}
