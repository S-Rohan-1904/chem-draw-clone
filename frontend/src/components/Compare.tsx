import { useState } from 'react'
import { Structure3D } from './Structure3D'
import type { Molecule } from '../types'

interface Props {
  base: Molecule
  other: Molecule
  title: string
  onClose: () => void
  onUse: (m: Molecule) => void
}

function labels(m: Molecule) {
  return [...m.stereo.centers.map((c) => `${c.symbol} ${c.label}`), ...m.stereo.double_bonds.map((b) => `C=C ${b.label}`)].join(', ') || 'none'
}

export function Compare({ base, other, title, onClose, onUse }: Props) {
  const [view, setView] = useState<'3d' | '2d'>('3d')
  const same = base.inchikey === other.inchikey
  return (
    <section className="card compare">
      <header className="card-head">
        <h2>{title}</h2>
        <div className="toolbar">
          <button type="button" className={view === '3d' ? 'active' : ''} onClick={() => setView('3d')}>3D</button>
          <button type="button" className={view === '2d' ? 'active' : ''} onClick={() => setView('2d')}>2D</button>
          <button type="button" onClick={() => onUse(other)}>Open this one</button>
          <button type="button" onClick={onClose}>Close</button>
        </div>
      </header>
      {same && <p className="warn">Same molecule: the mirror image is superimposable (meso or achiral).</p>}
      <div className="grid2">
        <div>
          <p className="compare-title">Original <span className="muted">{labels(base)}</span></p>
          {view === '3d' ? <Structure3D mol={base} highlight={null} compact /> : <div className="svg-wrap" dangerouslySetInnerHTML={{ __html: base.svg }} />}
        </div>
        <div>
          <p className="compare-title">{title} <span className="muted">{labels(other)}</span></p>
          {view === '3d' ? <Structure3D mol={other} highlight={null} compact /> : <div className="svg-wrap" dangerouslySetInnerHTML={{ __html: other.svg }} />}
        </div>
      </div>
    </section>
  )
}
