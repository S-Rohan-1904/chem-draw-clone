import { useState } from 'react'
import { api, describeFailure } from '../api'
import type { BatchRow } from '../types'

function csvEscape(v: unknown) {
  const s = v === undefined || v === null ? '' : String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function BatchPanel({ onOpen }: { onOpen: (name: string) => void }) {
  const [text, setText] = useState('')
  const [rows, setRows] = useState<BatchRow[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    const inputs = text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
    if (!inputs.length) return
    setBusy(true)
    setError(null)
    try {
      setRows((await api.batch(inputs.slice(0, 200))).rows)
    } catch (e) {
      setError(describeFailure(e))
    } finally {
      setBusy(false)
    }
  }

  const download = () => {
    if (!rows) return
    const head = ['input', 'ok', 'smiles', 'formula', 'mw', 'inchikey', 'stereo', 'unspecified', 'warning', 'error']
    const lines = [head.join(',')].concat(
      rows.map((r) => head.map((h) => csvEscape((r as unknown as Record<string, unknown>)[h])).join(',')),
    )
    const blob = new Blob([lines.join('\n') + '\n'], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'molecules.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const okCount = rows?.filter((r) => r.ok).length ?? 0

  return (
    <div className="batch">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={'One name or SMILES per line, up to 200\nethanol\n(2R)-butan-2-ol\n(E)-but-2-ene'}
        rows={6}
        spellCheck={false}
        aria-label="Names, one per line"
      />
      <div className="draw-actions">
        <button type="button" className="primary" onClick={() => void run()} disabled={busy || !text.trim()}>
          {busy ? 'Working...' : 'Run'}
        </button>
        {rows && <button type="button" onClick={download}>Download CSV</button>}
        {rows && <span className="muted small">{okCount} of {rows.length} parsed</span>}
        {error && <span className="hint-bad small">{error}</span>}
      </div>
      {rows && (
        <div className="table-wrap">
          <table className="batch-table">
            <thead>
              <tr><th>Input</th><th>Formula</th><th>MW</th><th>Stereo</th><th>SMILES</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className={r.ok ? '' : 'row-bad'}>
                  <td>
                    {r.input}
                    {r.warning && <div className="hint-warn small">{r.warning}</div>}
                    {!r.ok && (
                      <div className="hint-bad small">
                        {r.error}
                        {r.suggestions?.length ? (
                          <>
                            {' '}Did you mean{' '}
                            {r.suggestions.map((s) => (
                              <button key={s} type="button" className="link" onClick={() => setText((t) => t.replace(r.input, s))}>{s}</button>
                            ))}
                          </>
                        ) : null}
                      </div>
                    )}
                  </td>
                  <td>{r.formula ?? ''}</td>
                  <td>{r.mw ?? ''}</td>
                  <td className={r.unspecified ? 'hint-warn' : ''}>{r.stereo || (r.ok ? 'none' : '')}</td>
                  <td><code>{r.smiles ?? ''}</code></td>
                  <td>{r.ok && <button type="button" className="link" onClick={() => onOpen(r.input)}>Open</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
