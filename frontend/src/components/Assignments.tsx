import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, describeFailure } from '../api'
import type { Assignment, AssignmentProgress, AuthState } from '../types'
import { WorksheetButton } from './WorksheetButton'

interface Props {
  auth: AuthState | null
  onOpen: (name: string) => void
  onLogin: () => void
}

export function Assignments({ auth, onOpen, onLogin }: Props) {
  const [mine, setMine] = useState<Assignment[]>([])
  const [joined, setJoined] = useState<Assignment[]>([])
  const [current, setCurrent] = useState<Assignment | null>(null)
  const [progress, setProgress] = useState<AssignmentProgress | null>(null)
  const [code, setCode] = useState('')
  const [title, setTitle] = useState('')
  const [names, setNames] = useState('')
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([])
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const reload = useCallback(async () => {
    if (!auth) return
    try {
      const [m, j] = await Promise.all([api.myAssignments(auth), api.joinedAssignments(auth)])
      setMine(m)
      setJoined(j.filter((a) => !m.some((x) => x.id === a.id)))
    } catch {
      /* ignore */
    }
  }, [auth])

  useEffect(() => {
    void reload()
  }, [reload])

  // Shared link: /?assignment=CODE
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get('assignment')
    if (c) {
      setCode(c.toUpperCase())
      void open(c)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth])

  const open = async (c: string) => {
    setMsg(null)
    setProgress(null)
    try {
      const a = await api.getAssignment(c.trim(), auth)
      setCurrent(a)
      if (a.mine && auth) setProgress(await api.assignmentProgress(auth, a.code))
    } catch (e) {
      setMsg(describeFailure(e))
    }
  }

  const create = async (e: FormEvent) => {
    e.preventDefault()
    if (!auth) return
    setBusy(true)
    setMsg(null)
    try {
      const res = await api.createAssignment(auth, title.trim(), names.split(/\r?\n/).map((s) => s.trim()).filter(Boolean))
      setRejected(res.rejected)
      setTitle('')
      setNames('')
      await reload()
      setCurrent(res.assignment)
      setProgress(await api.assignmentProgress(auth, res.assignment.code))
    } catch (err) {
      setMsg(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [attempts, setAttempts] = useState<Record<number, number>>({})
  const [feedback, setFeedback] = useState<Record<number, { ok: boolean; text: string }>>({})

  const answer = async (itemId: number) => {
    if (!auth || !current) return
    const text = (answers[itemId] ?? '').trim()
    if (!text) return
    const n = (attempts[itemId] ?? 0) + 1
    setAttempts((a) => ({ ...a, [itemId]: n }))
    try {
      const res = await api.answerAssignment(auth, current.code, itemId, text, n)
      setFeedback((f) => ({ ...f, [itemId]: { ok: res.correct, text: res.message } }))
      setCurrent(res.assignment)
      if (res.assignment.mine) setProgress(await api.assignmentProgress(auth, res.assignment.code))
      void reload()
    } catch (e) {
      setFeedback((f) => ({ ...f, [itemId]: { ok: false, text: describeFailure(e) } }))
    }
  }

  const remove = async () => {
    if (!auth || !current) return
    await api.deleteAssignment(auth, current.code)
    setCurrent(null)
    void reload()
  }

  return (
    <div className="assignments">
      <div className="grid2">
        <section className="card">
          <header className="card-head"><h2>Join an assignment</h2></header>
          <form className="draw-actions" onSubmit={(e) => { e.preventDefault(); void open(code) }}>
            <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder="Code, e.g. K7PQ2M" aria-label="Assignment code" maxLength={8} />
            <button type="submit" className="primary" disabled={!code.trim()}>Open</button>
          </form>
          {!auth && <p className="muted small">You can view an assignment without an account. <button type="button" className="link" onClick={onLogin}>Log in</button> to record your progress.</p>}
          {joined.length > 0 && (
            <ul className="list">
              {joined.map((a) => (
                <li key={a.id}>
                  <button type="button" className="list-btn" onClick={() => void open(a.code)}>
                    <span className="list-title">{a.title}</span>
                    <span className="list-sub">{a.done_count} of {a.items.length} done · by {a.owner}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <header className="card-head"><h2>Create an assignment</h2></header>
          {auth ? (
            <form className="quiz-form" onSubmit={create}>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" aria-label="Title" required />
              <textarea value={names} onChange={(e) => setNames(e.target.value)} placeholder={'One name per line\n(2R)-butan-2-ol\n(E)-but-2-ene'} rows={5} aria-label="Names" required />
              <div className="draw-actions">
                <button type="submit" className="primary" disabled={busy || !title.trim() || !names.trim()}>{busy ? 'Checking names...' : 'Create'}</button>
              </div>
            </form>
          ) : (
            <p className="muted">Log in to create assignments and share a code with your class.</p>
          )}
          {rejected.length > 0 && (
            <p className="hint-bad small">Skipped: {rejected.map((r) => `${r.name} (${r.reason})`).join('; ')}</p>
          )}
          {mine.length > 0 && (
            <ul className="list">
              {mine.map((a) => (
                <li key={a.id}>
                  <button type="button" className="list-btn" onClick={() => void open(a.code)}>
                    <span className="list-title">{a.title} <code>{a.code}</code></span>
                    <span className="list-sub">{a.items.length} molecule{a.items.length === 1 ? '' : 's'}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {msg && <p className="error">{msg}</p>}

      {current && (
        <section className="card">
          <header className="card-head">
            <h2>{current.title} <span className="tag">code {current.code}</span></h2>
            <div className="toolbar">
              <span className="muted small">by {current.owner}{auth ? ` · ${current.done_count} of ${current.items.length} done` : ''}</span>
              <button type="button" onClick={() => void navigator.clipboard?.writeText(`${window.location.origin}/?assignment=${current.code}`)}>Copy link</button>
              <WorksheetButton title={current.title} items={current.items.map((i) => ({ name: i.name, smiles: i.smiles }))} />
              {current.mine && <button type="button" onClick={() => void remove()}>Delete</button>}
            </div>
          </header>
          {!current.mine && !auth && <p className="warn">Log in to answer. Your progress is recorded per account.</p>}
          <div className="assignment-grid">
            {current.items.map((it, idx) => (
              <div key={it.id} className={`card assignment-item ${it.done ? 'done' : ''}`}>
                <header className="card-head">
                  <h3>{idx + 1}. {current.mine || it.done ? it.name : 'Name this structure'}</h3>
                  <span className="muted small">{it.formula}{it.done ? ` · solved in ${it.attempts} attempt${it.attempts === 1 ? '' : 's'}` : ''}</span>
                </header>
                <div className="svg-wrap assignment-svg" dangerouslySetInnerHTML={{ __html: it.svg }} />
                {current.mine || it.done ? (
                  <div className="draw-actions">
                    <button type="button" className="link" onClick={() => onOpen(it.name)}>Open in viewer</button>
                  </div>
                ) : auth ? (
                  <form
                    className="draw-actions"
                    onSubmit={(e) => {
                      e.preventDefault()
                      void answer(it.id)
                    }}
                  >
                    <input
                      value={answers[it.id] ?? ''}
                      onChange={(e) => setAnswers((a) => ({ ...a, [it.id]: e.target.value }))}
                      placeholder="IUPAC name"
                      aria-label={`Answer ${idx + 1}`}
                      style={{ flex: '1 1 200px' }}
                      spellCheck={false}
                    />
                    <button type="submit" className="primary" disabled={!(answers[it.id] ?? '').trim()}>Check</button>
                  </form>
                ) : null}
                {feedback[it.id] && !it.done && <p className={`small ${feedback[it.id].ok ? 'hint-ok' : 'hint-bad'}`}>{feedback[it.id].text}</p>}
                {it.done && <p className="small hint-ok">Correct.</p>}
              </div>
            ))}
          </div>
          {progress && (
            <div className="table-wrap">
              <table className="batch-table">
                <thead>
                  <tr><th>Student</th>{progress.items.map((i) => <th key={i.id} title={i.name}>{i.name.length > 18 ? i.name.slice(0, 16) + '…' : i.name}</th>)}<th>Done</th></tr>
                  <tr><td className="muted small" colSpan={progress.items.length + 2}>Ticks show the number of attempts needed.</td></tr>
                </thead>
                <tbody>
                  {progress.participants.length === 0 && <tr><td colSpan={progress.items.length + 2} className="muted">No one has started yet.</td></tr>}
                  {progress.participants.map((p) => (
                    <tr key={p.username}>
                      <td>{p.username}</td>
                      {progress.items.map((i) => <td key={i.id}>{p.done.includes(i.id) ? `✓ (${p.attempts[String(i.id)] ?? 1})` : ''}</td>)}
                      <td>{p.count} / {progress.items.length}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
