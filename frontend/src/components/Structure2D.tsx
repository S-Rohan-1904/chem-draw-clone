import type { Molecule } from '../types'

export function Structure2D({ mol, svg, caption }: { mol: Molecule; svg?: string | null; caption?: string | null }) {
  return (
    <section className="card">
      <header className="card-head">
        <h2>2D structure</h2>
        {caption && <span className="muted">{caption}</span>}
      </header>
      <div className="svg-wrap" dangerouslySetInnerHTML={{ __html: svg ?? mol.svg }} />
    </section>
  )
}
