import { EXAMPLES } from '../examples'

export function Gallery({ onPick }: { onPick: (name: string) => void }) {
  return (
    <section className="card">
      <header className="card-head"><h2>Examples</h2></header>
      <ul className="list">
        {EXAMPLES.map((ex) => (
          <li key={ex.name}>
            <button type="button" className="list-btn" title={ex.name} onClick={() => onPick(ex.name)}>
              <span className="list-title">{ex.label}</span>
              <span className="list-sub">{ex.name}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
