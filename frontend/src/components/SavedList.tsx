import { useEffect, useState } from 'react'
import { ApiError } from '../api'
import { toolsApi } from '../tools/api'
import type { SearchResult } from '../tools/types'
import type { AuthState, SavedMolecule } from '../types'
import { WorksheetButton } from './WorksheetButton'

interface Props {
  auth: AuthState
  items: SavedMolecule[]
  onPick: (item: SavedMolecule) => void
  onDelete: (id: number) => void
  onUpdate: (id: number, patch: { notes?: string; collection?: string; label?: string }) => Promise<void>
}

function groupBy(items: SavedMolecule[]) {
  const map = new Map<string, SavedMolecule[]>()
  for (const it of items) {
    const key = it.collection || ''
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(it)
  }
  return [...map.entries()].sort(([a], [b]) => (a === '' ? 1 : b === '' ? -1 : a.localeCompare(b)))
}

export function SavedList({ auth, items, onPick, onDelete, onUpdate }: Props) {
  const [open, setOpen] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [collDraft, setCollDraft] = useState('')
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResult | null>(null)
  const [searchErr, setSearchErr] = useState<string | null>(null)
  const collections = [...new Set(items.map((i) => i.collection).filter(Boolean))].sort()

  // Structure search over the saved list: substructure when the query is
  // found in something, otherwise ranked by similarity. Debounced.
  useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResult(null)
      setSearchErr(null)
      return
    }
    const t = window.setTimeout(() => {
      toolsApi.search(auth, q)
        .then((r) => { setResult(r); setSearchErr(null) })
        .catch((e) => { setResult(null); setSearchErr(e instanceof ApiError && e.status === 400 ? 'Not a SMILES or SMARTS query.' : 'Search failed.') })
    }, 350)
    return () => window.clearTimeout(t)
  }, [query, auth, items.length])

  const score = result ? new Map(result.hits.map((h) => [h.id, h.score])) : null
  const shown = score ? items.filter((i) => score.has(i.id)).sort((a, b) => (score.get(b.id) ?? 0) - (score.get(a.id) ?? 0)) : items

  const expand = (it: SavedMolecule) => {
    if (open === it.id) {
      setOpen(null)
      return
    }
    setOpen(it.id)
    setDraft(it.notes)
    setCollDraft(it.collection)
  }

  const commit = async (it: SavedMolecule) => {
    if (draft !== it.notes || collDraft !== it.collection) await onUpdate(it.id, { notes: draft, collection: collDraft })
    setOpen(null)
  }

  return (
    <section className="card">
      <header className="card-head"><h2>Saved</h2><span className="muted small">{items.length}</span></header>
      {items.length === 0 && <p className="muted">Nothing saved yet.</p>}
      {items.length > 1 && (
        <div className="saved-search">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by structure: SMILES or SMARTS" aria-label="Structure search" spellCheck={false} />
          {result && <span className="muted small">{result.mode === 'substructure' ? `${result.hits.length} containing it` : `${result.hits.length} similar, best first`}</span>}
          {searchErr && <span className="hint-bad small">{searchErr}</span>}
        </div>
      )}
      {score && shown.length === 0 && !searchErr && <p className="muted small">No saved molecule matches.</p>}
      {groupBy(shown).map(([coll, rows]) => (
        <div key={coll || '__none'} className="collection">
          <div className="collection-head">
            {coll && <h3 className="collection-title">{coll}</h3>}
            <WorksheetButton title={coll || 'Saved molecules'} items={rows.map((r) => ({ name: r.label, smiles: r.smiles }))} />
          </div>
          <ul className="list">
            {rows.map((it) => (
              <li key={it.id} className="list-item">
                <div className="list-row">
                  <button type="button" className="list-btn" title={it.input_text} onClick={() => onPick(it)}>
                    <span className="list-title">{it.label}</span>
                    <span className="list-sub">{score && result?.mode === 'similarity' ? `${Math.round((score.get(it.id) ?? 0) * 100)}% similar · ` : ''}{it.notes ? it.notes : it.input_text}</span>
                  </button>
                  <button type="button" className="icon" aria-label={`Edit ${it.label}`} title="Notes and collection" onClick={() => expand(it)}>{open === it.id ? '−' : '✎'}</button>
                  <button type="button" className="icon" aria-label={`Delete ${it.label}`} title="Delete" onClick={() => onDelete(it.id)}>×</button>
                </div>
                {open === it.id && (
                  <div className="saved-edit">
                    <input list="collections" value={collDraft} onChange={(e) => setCollDraft(e.target.value)} placeholder="Collection" aria-label="Collection" />
                    <textarea value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Notes" rows={3} aria-label="Notes" />
                    <div className="saved-edit-actions">
                      <button type="button" className="primary" onClick={() => void commit(it)}>Done</button>
                      <button type="button" onClick={() => setOpen(null)}>Cancel</button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
      <datalist id="collections">
        {collections.map((c) => <option key={c} value={c} />)}
      </datalist>
    </section>
  )
}
