import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Molecule, NameBreakdown as Breakdown } from '../types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

export function NameBreakdown({ mol, onHighlight }: Props) {
  const [data, setData] = useState<Breakdown | null>(null)

  useEffect(() => {
    setData(null)
    if (mol.source !== 'iupac') return
    api.breakdown(mol.input_text, mol.smiles).then(setData).catch(() => setData(null))
  }, [mol])

  if (!data || mol.source !== 'iupac') return null
  const recognised = data.tokens.filter((t) => t.kind !== 'sep' && t.kind !== 'other').length
  if (recognised === 0) return null

  return (
    <section className="card">
      <header className="card-head">
        <h2>Name breakdown</h2>
        <span className="muted small">hover a part to highlight its atoms</span>
      </header>
      <p className="name-tokens">
        {data.tokens.map((t, i) =>
          t.kind === 'sep' ? (
            <span key={i}>{t.text}</span>
          ) : (
            <span
              key={i}
              className={`name-token kind-${t.kind}`}
              style={{ '--c': data.colours[t.kind] || '#9ca3af' } as React.CSSProperties}
              title={data.legend.find((l) => l.kind === t.kind)?.text}
              onMouseEnter={() => t.atoms && t.atoms.length && onHighlight(t.atoms, data.colours[t.kind])}
              onMouseLeave={() => onHighlight(null)}
            >
              {t.text}
            </span>
          ),
        )}
      </p>
      <ul className="legend">
        {data.legend.map((l) => (
          <li key={l.kind}><span className="swatch" style={{ background: l.colour }} /> {l.text}</li>
        ))}
      </ul>
    </section>
  )
}
