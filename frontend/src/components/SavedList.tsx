import type { SavedMolecule } from '../types'

interface Props {
  items: SavedMolecule[]
  onPick: (item: SavedMolecule) => void
  onDelete: (id: number) => void
}

export function SavedList({ items, onPick, onDelete }: Props) {
  return (
    <section className="card">
      <header className="card-head"><h2>Saved</h2></header>
      {items.length === 0 && <p className="muted">Nothing saved yet.</p>}
      <ul className="list">
        {items.map((it) => (
          <li key={it.id} className="list-row">
            <button type="button" className="list-btn" title={it.input_text} onClick={() => onPick(it)}>
              <span className="list-title">{it.label}</span>
              <span className="list-sub">{it.input_text}</span>
            </button>
            <button type="button" className="icon" aria-label={`Delete ${it.label}`} title="Delete" onClick={() => onDelete(it.id)}>×</button>
          </li>
        ))}
      </ul>
    </section>
  )
}
