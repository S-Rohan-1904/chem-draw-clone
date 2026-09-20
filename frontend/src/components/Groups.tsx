import type { FunctionalGroup, Molecule } from '../types'

interface Props {
  mol: Molecule
  active: string | null
  onSelect: (group: FunctionalGroup | null) => void
}

export function Groups({ mol, active, onSelect }: Props) {
  const groups = mol.groups ?? []
  return (
    <section className="card">
      <header className="card-head">
        <h2>Functional groups</h2>
        {active && <button type="button" className="link" onClick={() => onSelect(null)}>Clear</button>}
      </header>
      {groups.length === 0 && <p className="muted">None detected.</p>}
      <div className="chips">
        {groups.map((g) => (
          <button
            key={g.name}
            type="button"
            className={`chip chip-group ${active === g.name ? 'active' : ''}`}
            style={{ '--c': g.colour } as React.CSSProperties}
            onClick={() => onSelect(active === g.name ? null : g)}
          >
            <span className="swatch" />
            {g.name}
            {g.atoms.length > 1 && <span className="count">{g.atoms.length}</span>}
          </button>
        ))}
      </div>
    </section>
  )
}
