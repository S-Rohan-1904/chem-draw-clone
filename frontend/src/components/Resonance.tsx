import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Molecule } from '../types'

export function Resonance({ mol }: { mol: Molecule }) {
  const [forms, setForms] = useState<{ svg: string; smiles: string }[]>([])
  const [i, setI] = useState(0)

  useEffect(() => {
    setForms([])
    setI(0)
    api.resonance(mol.smiles).then((r) => setForms(r.forms)).catch(() => setForms([]))
  }, [mol.smiles])

  if (forms.length < 2) return null
  return (
    <section className="card">
      <header className="card-head">
        <h2>Resonance forms</h2>
        <div className="toolbar">
          <button type="button" onClick={() => setI((i - 1 + forms.length) % forms.length)} aria-label="Previous form">‹</button>
          <span className="muted small">{i + 1} of {forms.length}</span>
          <button type="button" onClick={() => setI((i + 1) % forms.length)} aria-label="Next form">›</button>
        </div>
      </header>
      <div className="resonance-strip">
        {forms.map((f, k) => (
          <button key={k} type="button" className={`resonance-thumb ${k === i ? 'active' : ''}`} onClick={() => setI(k)} aria-label={`Form ${k + 1}`}>
            <div dangerouslySetInnerHTML={{ __html: f.svg }} />
          </button>
        ))}
      </div>
      <p className="muted small">Same atoms and layout in every form; only bonds and charges move. Kekulé structures count as separate forms.</p>
    </section>
  )
}
