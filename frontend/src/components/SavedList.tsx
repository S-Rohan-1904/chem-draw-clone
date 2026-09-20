import { useState } from 'react'
import type { SavedMolecule } from '../types'

interface Props {
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

export function SavedList({ items, onPick, onDelete, onUpdate }: Props) {
  const [open, setOpen] = useState<number | null>(null)
  const [draft, setDraft] = useState('')
  const [collDraft, setCollDraft] = useState('')
  const collections = [...new Set(items.map((i) => i.collection).filter(Boolean))].sort()

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
      {groupBy(items).map(([coll, rows]) => (
        <div key={coll || '__none'} className="collection">
          {coll && <h3 className="collection-title">{coll}</h3>}
          <ul className="list">
            {rows.map((it) => (
              <li key={it.id} className="list-item">
                <div className="list-row">
                  <button type="button" className="list-btn" title={it.input_text} onClick={() => onPick(it)}>
                    <span className="list-title">{it.label}</span>
                    <span className="list-sub">{it.notes ? it.notes : it.input_text}</span>
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
