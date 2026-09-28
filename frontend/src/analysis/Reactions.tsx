import { useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { RecordedReaction, RecordedReactions } from './types'

interface Props {
  mol: Molecule
  onOpen: (smiles: string) => void
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

/** Recorded reactions for the molecule, from US patent records. */
export function Reactions({ mol, onOpen, onHighlight }: Props) {
  const [rx, setRx] = useState<RecordedReactions | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setRx(null)
    setError(null)
    analysisApi.reactions(mol.smiles)
      .then((d) => live && setRx(d))
      .catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [mol.smiles])

  return (
    <section className="card">
      <header className="card-head">
        <h2>Reactions</h2>
      </header>
      {error && <p className="warn">{error}</p>}
      {!error && !rx && <p className="muted small">Loading…</p>}
      {rx && <RecordedTab data={rx} onOpen={onOpen} onHighlight={onHighlight} />}
    </section>
  )
}

function RecordedTab({ data, onOpen, onHighlight }: { data: RecordedReactions; onOpen: Props['onOpen']; onHighlight: Props['onHighlight'] }) {
  if (!data.available) {
    return <p className="muted">The reaction index is not installed on this server.</p>
  }
  return (
    <div className="bonding-body">
      {data.uses.length === 0 && data.makes.length === 0 && (
        data.heavy_atoms && data.max_atoms && data.heavy_atoms > data.max_atoms ? (
          <p className="muted small">
            This molecule has {data.heavy_atoms} heavy atoms, and the reaction index covers molecules up to {data.max_atoms}.
          </p>
        ) : (
          <p className="muted small">
            This molecule is not in the reaction records used here. They cover mostly drug and fine-chemical
            synthesis from patents and papers, plus enzyme reactions, so simple hydrocarbons and uncommon
            natural products are often absent.
          </p>
        )
      )}
      {data.stereo_ignored && (
        <p className="muted small">There is no record for this exact stereoisomer, so reactions of the same structure with any stereochemistry are shown.</p>
      )}
      <Section title="Used in" empty="No recorded reactions use this molecule as a starting material." items={data.uses} direction="uses" onOpen={onOpen} onHighlight={onHighlight} />
      <Section title="Made by" empty="No recorded reactions make this molecule." items={data.makes} direction="makes" onOpen={onOpen} onHighlight={onHighlight} />
      {data.enzyme_uses.length > 0 && (
        <Section title="Used in by enzymes" empty="" items={data.enzyme_uses} direction="uses" enzyme onOpen={onOpen} onHighlight={onHighlight} />
      )}
      {data.enzyme_makes.length > 0 && (
        <Section title="Made by enzymes" empty="" items={data.enzyme_makes} direction="makes" enzyme onOpen={onOpen} onHighlight={onHighlight} />
      )}
      <p className="muted small">
        Reaction types are ranked by how many distinct recorded reactions show them. Each has one real example, preferring the simplest one that reports a yield.
        Sources: {data.sources.map((src, i) => (
          <span key={src.url}>
            {i > 0 && ', '}
            <a href={src.url} target="_blank" rel="noopener noreferrer">{src.author}, {src.name}</a> ({src.licence})
          </span>
        ))}.
        Most entries are text-mined from patents, so an occasional one is wrong.
      </p>
    </div>
  )
}

function Section({ title, empty, items, direction, enzyme = false, onOpen, onHighlight }: {
  title: string
  empty: string
  items: RecordedReaction[]
  direction: 'uses' | 'makes'
  enzyme?: boolean
  onOpen: Props['onOpen']
  onHighlight: Props['onHighlight']
}) {
  return (
    <>
      <h3>{title}</h3>
      {items.length === 0 && <p className="muted small">{empty}</p>}
      <ol className="rxn-rows recorded">
        {items.map((r) => {
          const others = direction === 'uses' ? r.products.slice(0, 1) : r.reactants
          return (
            <li key={r.label} className="rxn-row recorded" onMouseEnter={() => r.atoms.length && onHighlight(r.atoms, '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
              <div className="rxn-info">
                <b>{r.label}</b>
                <span className="muted small">seen in {r.count} {enzyme ? 'enzyme' : 'recorded'} reaction{r.count === 1 ? '' : 's'}</span>
                <span className="small">
                  Example: {r.ref_url ? <a href={r.ref_url} target="_blank" rel="noopener noreferrer">{r.ref_label}</a> : r.ref_label}
                  {r.year ? ` (${r.year})` : ''}
                  {r.yield != null ? `, ${Math.round(r.yield)}% yield` : ''}
                  {r.ec.length > 0 && <>, EC {r.ec.map((ec, i) => (
                    <span key={ec}>{i > 0 && ' '}<a href={`https://enzyme.expasy.org/EC/${ec}`} target="_blank" rel="noopener noreferrer">{ec}</a></span>
                  ))}</>}
                </span>
                <span className="rxn-open">
                  {others.map((s) => (
                    <button key={s} type="button" className="link small" title={s} onClick={() => onOpen(s)}>
                      Open {direction === 'uses' ? 'product' : 'starting material'}
                    </button>
                  ))}
                </span>
              </div>
              {r.svg && <div className="rxn-scheme" dangerouslySetInnerHTML={{ __html: r.svg }} />}
            </li>
          )
        })}
      </ol>
    </>
  )
}
