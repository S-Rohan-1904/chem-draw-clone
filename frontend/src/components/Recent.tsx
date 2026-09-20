import type { Molecule } from '../types'

export interface RecentItem {
  input: string
  inchikey: string
  formula: string
  at: number
}

const KEY = 'chem.recent'
const MAX = 20

export function loadRecent(): RecentItem[] {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as RecentItem[]) : []
  } catch {
    return []
  }
}

export function pushRecent(mol: Molecule): RecentItem[] {
  const input = mol.source === 'molfile' ? mol.smiles : mol.input_text
  const next = [{ input, inchikey: mol.inchikey, formula: mol.formula, at: Date.now() }, ...loadRecent().filter((r) => r.inchikey !== mol.inchikey)].slice(0, MAX)
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* storage unavailable */
  }
  return next
}

export function clearRecent(): RecentItem[] {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* storage unavailable */
  }
  return []
}

interface Props {
  items: RecentItem[]
  onPick: (input: string) => void
  onClear: () => void
}

export function Recent({ items, onPick, onClear }: Props) {
  if (items.length === 0) return null
  return (
    <section className="card">
      <header className="card-head">
        <h2>Recent</h2>
        <button type="button" className="link" onClick={onClear}>Clear</button>
      </header>
      <ul className="list">
        {items.map((it) => (
          <li key={it.inchikey}>
            <button type="button" className="list-btn" title={it.input} onClick={() => onPick(it.input)}>
              <span className="list-title">{it.input}</span>
              <span className="list-sub">{it.formula}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
