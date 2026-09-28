import { useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { Literature as LiteratureData } from './types'

/** ChemRxiv preprints about the molecule. */
export function Literature({ mol }: { mol: Molecule }) {
  const [lit, setLit] = useState<LiteratureData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setLit(null)
    setError(null)
    // A typed name is a fallback search term when PubChem has no name for the structure.
    const name = ['iupac', 'pubchem', 'cactus'].includes(mol.source) ? mol.input_text : ''
    analysisApi.literature(mol.smiles, name)
      .then((d) => live && setLit(d))
      .catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [mol.smiles, mol.source, mol.input_text])

  return (
    <section className="card">
      <header className="card-head">
        <h2>Literature</h2>
      </header>
      {error && <p className="warn">{error}</p>}
      {!error && !lit && <p className="muted small">Loading…</p>}
      {lit && <ChemRxivList data={lit} />}
    </section>
  )
}

function ChemRxivList({ data }: { data: LiteratureData }) {
  if (!data.available) return <p className="muted">{data.reason}</p>
  return (
    <div className="bonding-body">
      {data.match === 'fulltext' && data.items.length > 0 && (
        <p className="muted small">No ChemRxiv title or abstract names “{data.query}”, so these preprints are ones that mention it in the text.</p>
      )}
      {data.items.length === 0 ? (
        <p className="muted">No ChemRxiv preprints found for “{data.query}”.</p>
      ) : (
        <ol className="lit-list">
          {data.items.map((p) => (
            <li key={p.doi}>
              <a href={p.url} target="_blank" rel="noopener noreferrer"><b>{p.title}</b></a>
              <span className="muted small">
                {[p.authors, p.date, p.cited_by != null ? `cited ${p.cited_by}×` : ''].filter(Boolean).join(' · ')}
              </span>
            </li>
          ))}
        </ol>
      )}
      <p className="muted small">Searched ChemRxiv for “{data.query}”{data.source ? ` via ${data.source}` : ''}. Preprints are not peer reviewed. Links open the ChemRxiv page.</p>
    </div>
  )
}
