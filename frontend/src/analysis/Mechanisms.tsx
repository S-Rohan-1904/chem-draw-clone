import { useEffect, useState } from 'react'
import { analysisApi } from './api'
import type { MechanismDetail, MechanismSummary } from './types'
import './analysis.css'

export function MechanismsPanel({ onOpen }: { onOpen: (smiles: string) => void }) {
  const [list, setList] = useState<MechanismSummary[]>([])
  const [id, setId] = useState<string | null>(null)
  const [detail, setDetail] = useState<MechanismDetail | null>(null)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    analysisApi.mechanisms().then((r) => {
      setList(r.mechanisms)
      if (r.mechanisms.length && !id) setId(r.mechanisms[0].id)
    }).catch(() => setError('Could not load the mechanism list.'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!id) return
    setDetail(null)
    setStep(0)
    analysisApi.mechanism(id).then(setDetail).catch(() => setError('Could not load this mechanism.'))
  }, [id])

  const categories = Array.from(new Set(list.map((m) => m.category)))
  const current = detail?.steps[step]

  return (
    <div className="mech-layout">
      <aside className="card mech-list">
        <h2>Mechanisms</h2>
        {error && <p className="error small">{error}</p>}
        {categories.map((c) => (
          <div key={c} className="mech-group">
            <h3>{c}</h3>
            <ul>
              {list.filter((m) => m.category === c).map((m) => (
                <li key={m.id}>
                  <button type="button" className={`mech-item ${id === m.id ? 'active' : ''}`} onClick={() => setId(m.id)}>
                    <span>{m.name}</span>
                    <span className="muted small">{m.steps} steps</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </aside>
      <main className="card mech-main">
        {!detail && <p className="muted">Loading...</p>}
        {detail && current && (
          <>
            <header className="card-head">
              <div>
                <h2>{detail.name}</h2>
                <p className="muted small">{detail.summary}</p>
              </div>
              <div className="toolbar">
                <button type="button" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>Previous</button>
                <span className="muted small">step {step + 1} of {detail.steps.length}</span>
                <button type="button" className="primary" onClick={() => setStep((s) => Math.min(detail.steps.length - 1, s + 1))} disabled={step === detail.steps.length - 1}>Next</button>
              </div>
            </header>
            <div className="mech-steps">
              {detail.steps.map((_, i) => (
                <button key={i} type="button" className={`mech-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`} onClick={() => setStep(i)} aria-label={`Step ${i + 1}`}>{i + 1}</button>
              ))}
            </div>
            <div className="svg-wrap mech-svg" dangerouslySetInnerHTML={{ __html: current.svg }} />
            <p className="mech-caption">{current.caption}</p>
            <div className="toolbar">
              {current.arrows > 0 && (
                <span className="muted small">
                  {current.half ? 'Fishhook arrows move one electron each.' : `${current.arrows} curved arrow${current.arrows > 1 ? 's' : ''}: each moves an electron pair from where it starts (a lone pair or a bond) to where it points (a new bond or an atom).`}
                </span>
              )}
              {step === detail.steps.length - 1 && (
                <button type="button" className="link" onClick={() => onOpen(current.smiles.split('.')[0].replace(/\[([A-Za-z]+)(H\d*)?([+-]?\d*)?:\d+\]/g, (_m, el: string, h: string | undefined, ch: string | undefined) => `[${el}${h ?? ''}${ch ?? ''}]`))}>Open the product on the Name tab</button>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
