import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
import type { AuthState, QuizAnswer, QuizQuestion } from '../types'

interface Props {
  auth: AuthState | null
  onOpen: (name: string) => void
}

const LEVELS = [
  { n: 1, label: 'Small molecules' },
  { n: 2, label: 'Functional groups' },
  { n: 3, label: 'Stereochemistry' },
]

export function QuizPanel({ auth, onOpen }: Props) {
  const [level, setLevel] = useState(1)
  const [q, setQ] = useState<QuizQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [attempt, setAttempt] = useState(1)
  const [result, setResult] = useState<QuizAnswer | null>(null)
  const [score, setScore] = useState({ right: 0, total: 0 })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const seen = useRef<string[]>([])

  const next = useCallback(async (lvl = level) => {
    setBusy(true)
    setError(null)
    setResult(null)
    setAnswer('')
    setAttempt(1)
    try {
      const question = await api.quizQuestion(lvl, seen.current.slice(-30))
      seen.current.push(question.id)
      setQ(question)
    } catch (e) {
      setQ(null)
      setError(e instanceof ApiError ? e.message : 'Could not load a question.')
    } finally {
      setBusy(false)
    }
  }, [level])

  useEffect(() => {
    void next(level)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [level])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!q || !answer.trim() || busy) return
    setBusy(true)
    try {
      const res = await api.quizAnswer(auth, { id: q.id, answer: answer.trim(), attempt })
      setResult(res)
      if (res.correct) setScore((s) => ({ right: s.right + 1, total: s.total + 1 }))
      else if (res.verdict !== 'unparsed') setAttempt((a) => a + 1)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const reveal = async () => {
    if (!q) return
    const res = await api.quizAnswer(auth, { id: q.id, answer: '-', attempt, reveal: true })
    setResult(res)
    setScore((s) => ({ right: s.right, total: s.total + 1 }))
  }

  const done = result?.correct || result?.verdict === 'revealed'

  return (
    <div className="quiz">
      <div className="quiz-bar">
        <div className="toolbar">
          {LEVELS.map((l) => (
            <button key={l.n} type="button" className={level === l.n ? 'active' : ''} onClick={() => setLevel(l.n)}>
              {l.n}. {l.label}
            </button>
          ))}
        </div>
        <span className="muted">Score {score.right} / {score.total}{auth ? '' : ' (log in to keep history)'}</span>
      </div>
      {error && <p className="error">{error}</p>}
      {q && (
        <div className="grid2 quiz-grid">
          <section className="card">
            <header className="card-head">
              <h2>Name this structure</h2>
              <span className="muted">{q.formula}{q.stereo_count ? ` · ${q.stereo_count} stereo element${q.stereo_count > 1 ? 's' : ''}` : ''}</span>
            </header>
            <div className="svg-wrap" dangerouslySetInnerHTML={{ __html: q.svg }} />
          </section>
          <section className="card">
            <header className="card-head"><h2>Your answer</h2><span className="muted small">Attempt {attempt}</span></header>
            <form className="quiz-form" onSubmit={submit}>
              <input
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="IUPAC name"
                aria-label="Your answer"
                disabled={!!done}
                spellCheck={false}
                autoFocus
              />
              <div className="draw-actions">
                <button type="submit" className="primary" disabled={busy || !answer.trim() || !!done}>Check</button>
                {!done && <button type="button" onClick={() => void reveal()} disabled={busy}>Show answer</button>}
                {done && <button type="button" className="primary" onClick={() => void next()}>Next</button>}
                {!done && <button type="button" onClick={() => void next()} disabled={busy}>Skip</button>}
              </div>
            </form>
            {result && (
              <div className={`quiz-feedback ${result.correct ? 'ok' : result.verdict === 'stereo' ? 'warn' : 'bad'}`}>
                <p>{result.message}</p>
                {done && result.accepted.length > 0 && (
                  <p>
                    Accepted: {result.accepted.slice(0, 3).map((n, i) => (
                      <span key={n}>{i > 0 && ', '}<button type="button" className="link" onClick={() => onOpen(n)}>{n}</button></span>
                    ))}
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
