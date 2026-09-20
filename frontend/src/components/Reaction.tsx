import { ReactionClass } from '../analysis/ReactionClass'
import { Stoichiometry } from '../tools/Stoichiometry'
import type { ReactionResult } from '../types'

interface Props {
  text: string
  rxn: ReactionResult
  onOpen: (smiles: string) => void
}

function Side({ title, items, onOpen }: { title: string; items: { smiles: string; formula: string }[]; onOpen: (s: string) => void }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="rxn-side-title">{title}</h3>
      <ul className="rxn-list">
        {items.map((m, i) => (
          <li key={i}>
            <button type="button" className="link" onClick={() => onOpen(m.smiles)}><code>{m.smiles}</code></button> <span className="muted small">{m.formula}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Reaction({ text, rxn, onOpen }: Props) {
  const imbalance = Object.entries(rxn.imbalance)
  return (
    <section className="card">
      <header className="card-head">
        <h2>Reaction</h2>
        <span className={`tag ${rxn.balanced ? 'tag-ok' : 'tag-warn'}`}>
          {rxn.balanced ? 'atoms balanced' : `unbalanced: ${imbalance.map(([el, n]) => `${el} ${n > 0 ? '+' : ''}${n}`).join(', ')}`}
        </span>
      </header>
      <p className="muted small"><code>{text}</code></p>
      <div className="svg-wrap rxn-svg" dangerouslySetInnerHTML={{ __html: rxn.svg }} />
      <div className="rxn-sides">
        <Side title="Reactants" items={rxn.reactants} onOpen={onOpen} />
        <Side title="Agents" items={rxn.agents} onOpen={onOpen} />
        <Side title="Products" items={rxn.products} onOpen={onOpen} />
      </div>
      <Stoichiometry rxn={rxn} />
      <ReactionClass rxn={rxn} />
      {rxn.mapped && <p className="muted small">Atom map numbers in the input colour matching atoms on both sides; the small number by each atom is its map number.</p>}
    </section>
  )
}
