import type { Molecule } from '../types'

export function Structure2D({ mol }: { mol: Molecule }) {
  return (
    <section className="card">
      <header className="card-head">
        <h2>2D structure</h2>
      </header>
      <div className="svg-wrap" dangerouslySetInnerHTML={{ __html: mol.svg }} />
    </section>
  )
}
