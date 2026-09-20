import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import type { IsomerResult } from '../types'

const EXAMPLES = ['C4H10', 'C5H12', 'C6H14', 'C4H10O', 'C3H8O', 'C4H9Cl', 'C3H9N', 'C4H8', 'C3H6O']

export function Isomers({ onOpen }: { onOpen: (smiles: string) => void }) {
  const [formula, setFormula] = useState('C5H12')
  const [result, setResult] = useState<IsomerResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const run = async (f = formula) => {
    setBusy(true)
    setError(null)
    try {
      setResult(await api.isomers(f))
    } catch (e) {
      setResult(null)
      setError(e instanceof ApiError ? e.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void run()
  }

  return (
    <div className="isomers">
      <form className="name-input" onSubmit={submit}>
        <div className="input-wrap">
          <input value={formula} onChange={(e) => setFormula(e.target.value)} placeholder="Molecular formula, e.g. C4H10O" aria-label="Molecular formula" spellCheck={false} />
        </div>
        <button type="submit" disabled={busy || !formula.trim()}>{busy ? 'Working...' : 'List isomers'}</button>
      </form>
      <div className="chips">
        {EXAMPLES.map((f) => (
          <button key={f} type="button" className="chip chip-atom" onClick={() => { setFormula(f); void run(f) }}>{f}</button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <section className="card">
          <header className="card-head">
            <h2>{result.count} isomer{result.count === 1 ? '' : 's'} of {result.formula}</h2>
            <span className="muted small">{result.note}</span>
          </header>
          <div className="isomer-grid">
            {result.isomers.map((iso) => (
              <button key={iso.smiles} type="button" className="isomer-tile" title={iso.smiles} onClick={() => onOpen(iso.smiles)}>
                <div dangerouslySetInnerHTML={{ __html: iso.svg }} />
                <code>{iso.smiles}</code>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
