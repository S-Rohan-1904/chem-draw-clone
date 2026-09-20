import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'
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
      setMsg(e instanceof ApiError ? e.message : 'Request failed')
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
      setMsg(err instanceof ApiError ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  const toggle = async (itemId: number, done: boolean) => {
    if (!auth || !current) return
    const updated = await api.markDone(auth, current.code, itemId, done)
    setCurrent(updated)
    if (updated.mine) setProgress(await api.assignmentProgress(auth, updated.code))
    void reload()
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
          <ol className="assignment-items">
            {current.items.map((it) => (
              <li key={it.id} className={it.done ? 'done' : ''}>
                {auth && <input type="checkbox" checked={it.done} onChange={(e) => void toggle(it.id, e.target.checked)} aria-label={`Done: ${it.name}`} />}
                <button type="button" className="link" onClick={() => onOpen(it.name)}>{it.name}</button>
              </li>
            ))}
          </ol>
          {progress && (
            <div className="table-wrap">
              <table className="batch-table">
                <thead>
                  <tr><th>Student</th>{progress.items.map((i) => <th key={i.id} title={i.name}>{i.name.length > 18 ? i.name.slice(0, 16) + '…' : i.name}</th>)}<th>Done</th></tr>
                </thead>
                <tbody>
                  {progress.participants.length === 0 && <tr><td colSpan={progress.items.length + 2} className="muted">No one has started yet.</td></tr>}
                  {progress.participants.map((p) => (
                    <tr key={p.username}>
                      <td>{p.username}</td>
                      {progress.items.map((i) => <td key={i.id}>{p.done.includes(i.id) ? '✓' : ''}</td>)}
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
