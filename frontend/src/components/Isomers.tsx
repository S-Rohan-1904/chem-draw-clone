import { useState, type FormEvent } from 'react'
import { api, describeFailure } from '../api'
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
      setError(describeFailure(e))
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
            <h2>{result.count} constitutional isomer{result.count === 1 ? '' : 's'} of {result.formula}</h2>
            <span className="muted small">{result.note}</span>
          </header>
          {[false, true].map((cyclic) => {
            const group = result.isomers.filter((i) => i.cyclic === cyclic)
            if (group.length === 0) return null
            return (
              <div key={String(cyclic)}>
                {result.isomers.some((i) => i.cyclic) && <h3 className="collection-title">{cyclic ? 'Cyclic' : 'Acyclic'} ({group.length})</h3>}
                <div className="isomer-grid">
                  {group.map((iso) => (
                    <div key={iso.smiles} className="isomer-tile">
                      <button type="button" className="isomer-open" title="Open in viewer" onClick={() => onOpen(iso.smiles)}>
                        <div dangerouslySetInnerHTML={{ __html: iso.svg }} />
                        <code>{iso.smiles}</code>
                      </button>
                      {iso.stereo_count > 1 && (
                        <div className="isomer-stereo">
                          <span className="muted small">{iso.stereo_count} stereoisomers:</span>
                          {iso.stereoisomers.map((s) => (
                            <button key={s} type="button" className="link small" onClick={() => onOpen(s)}>{s}</button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </section>
      )}
    </div>
  )
}
