import { Suspense, lazy, useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import type { EditorHandle } from './KetcherEditor'
import { api, describeFailure } from '../api'
import type { AuthState, QuizAnswer, QuizQuestion, QuizStats } from '../types'

const KetcherEditor = lazy(() => import('./KetcherEditor'))
const TIME_LIMIT = 60

interface Props {
  auth: AuthState | null
  onOpen: (name: string) => void
}

const LEVELS = [
  { n: 1, label: 'Small molecules' },
  { n: 2, label: 'Functional groups' },
  { n: 3, label: 'Stereochemistry' },
  { n: 4, label: 'Draw it' },
]

function Progress({ auth, refresh }: { auth: AuthState; refresh: number }) {
  const [stats, setStats] = useState<QuizStats | null>(null)
  useEffect(() => {
    api.quizStats(auth).then(setStats).catch(() => setStats(null))
  }, [auth, refresh])
  if (!stats || stats.total === 0) return null
  const pct = Math.round((100 * stats.correct) / stats.total)
  return (
    <section className="card">
      <header className="card-head">
        <h2>My progress</h2>
        <span className="muted small">{stats.correct} of {stats.total} correct ({pct}%) · streak {stats.streak}</span>
      </header>
      <ul className="progress-list">
        {stats.recent.map((r, i) => (
          <li key={i} className={r.correct ? 'ok' : 'bad'}>
            <span className="mark">{r.correct ? '✓' : '✗'}</span>
            <span className="name">{r.name}</span>
            <span className="muted small">{r.attempts} attempt{r.attempts === 1 ? '' : 's'}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function QuizName({ id }: { id: string }) {
  const [name, setName] = useState<string | null>(null)
  useEffect(() => {
    setName(null)
    api.lookupName(id).then((r) => setName(r.found ? [r.title, r.iupac].filter(Boolean).join(' · ') : null)).catch(() => setName(null))
  }, [id])
  return name ? <p className="small">PubChem: {name}</p> : null
}

export function QuizPanel({ auth, onOpen }: Props) {
  const [level, setLevel] = useState(1)
  const [q, setQ] = useState<QuizQuestion | null>(null)
  const [answer, setAnswer] = useState('')
  const [attempt, setAttempt] = useState(1)
  const [result, setResult] = useState<QuizAnswer | null>(null)
  const [score, setScore] = useState({ right: 0, total: 0 })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [timed, setTimed] = useState(false)
  const [left, setLeft] = useState(TIME_LIMIT)
  const [refresh, setRefresh] = useState(0)
  const seen = useRef<string[]>([])
  const editor = useRef<EditorHandle | null>(null)
  const [editorReady, setEditorReady] = useState(false)

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
      setLeft(TIME_LIMIT)
      if (lvl === 4) void editor.current?.clear()
    } catch (e) {
      setQ(null)
      setError(describeFailure(e))
    } finally {
      setBusy(false)
    }
  }, [level])

  useEffect(() => {
    void next(level)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [level])

  const check = useCallback(async (value: string) => {
    if (!q || !value.trim() || busy) return
    setBusy(true)
    try {
      const res = await api.quizAnswer(auth, { id: q.id, answer: value, attempt })
      setResult(res)
      if (res.correct) {
        setScore((s) => ({ right: s.right + 1, total: s.total + 1 }))
        setRefresh((n) => n + 1)
      } else if (res.verdict !== 'unparsed') setAttempt((a) => a + 1)
    } catch (err) {
      setError(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }, [q, busy, auth, attempt])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (level === 4) {
      const mol = await editor.current?.getMolfile()
      if (mol && mol.includes('M  END')) void check(mol)
      return
    }
    void check(answer.trim())
  }

  const reveal = useCallback(async () => {
    if (!q) return
    const res = await api.quizAnswer(auth, { id: q.id, answer: '-', attempt, reveal: true })
    setResult(res)
    setScore((s) => ({ right: s.right, total: s.total + 1 }))
    setRefresh((n) => n + 1)
  }, [q, auth, attempt])

  const done = result?.correct || result?.verdict === 'revealed'

  // Countdown in timed mode; time out reveals the answer.
  useEffect(() => {
    if (!timed || !q || done) return
    if (left <= 0) {
      void reveal()
      return
    }
    const t = window.setTimeout(() => setLeft((l) => l - 1), 1000)
    return () => window.clearTimeout(t)
  }, [timed, q, done, left, reveal])

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
        <div className="toolbar">
          <label className="check"><input type="checkbox" checked={timed} onChange={(e) => { setTimed(e.target.checked); setLeft(TIME_LIMIT) }} /> Timed ({TIME_LIMIT} s)</label>
          {timed && q && !done && <span className={`timer ${left <= 10 ? 'urgent' : ''}`}>{left}s</span>}
          <span className="muted">Score {score.right} / {score.total}{auth ? '' : ' (log in to keep history)'}</span>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {auth && <Progress auth={auth} refresh={refresh} />}
      {q && (
        <div className="grid2 quiz-grid">
          <section className="card">
            <header className="card-head">
              <h2>{level === 4 ? 'Draw this molecule' : 'Name this structure'}</h2>
              <span className="muted">{q.formula}{q.stereo_count ? ` · ${q.stereo_count} stereo element${q.stereo_count > 1 ? 's' : ''}` : ''}</span>
            </header>
            {level === 4 ? <p className="quiz-name">{q.name}</p> : <div className="svg-wrap" dangerouslySetInnerHTML={{ __html: q.svg }} />}
          </section>
          <section className="card">
            <header className="card-head"><h2>Your answer</h2><span className="muted small">Attempt {attempt}</span></header>
            <form className="quiz-form" onSubmit={submit}>
              {level === 4 ? (
                <div className="editor-wrap quiz-editor">
                  <Suspense fallback={<div className="editor-loading">Loading editor...</div>}>
                    <KetcherEditor onReady={(h) => { editor.current = h; setEditorReady(true) }} onError={() => undefined} />
                  </Suspense>
                </div>
              ) : (
              <input
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="IUPAC name"
                aria-label="Your answer"
                disabled={!!done}
                spellCheck={false}
                autoFocus
              />
              )}
              <div className="draw-actions">
                <button type="submit" className="primary" disabled={busy || !!done || (level === 4 ? !editorReady : !answer.trim())}>Check</button>
                {!done && <button type="button" onClick={() => void reveal()} disabled={busy}>Show answer</button>}
                {done && <button type="button" className="primary" onClick={() => void next()}>Next</button>}
                {!done && <button type="button" onClick={() => void next()} disabled={busy}>Skip</button>}
              </div>
            </form>
            {result && (
              <div className={`quiz-feedback ${result.correct ? 'ok' : result.verdict === 'stereo' ? 'warn' : 'bad'}`}>
                <p>{result.message}</p>
                {done && <QuizName id={q.id} />}
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
