import { type ReactNode, useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { LinkedCompound, Manufacture, RecordedReaction, RecordedReactions, WikipediaMaking } from './types'

interface Props {
  mol: Molecule
  onOpen: (smiles: string) => void
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

/** Recorded reactions for the molecule, from US patent records. */
export function Reactions({ mol, onOpen, onHighlight }: Props) {
  const [rx, setRx] = useState<RecordedReactions | null>(null)
  const [made, setMade] = useState<Manufacture | null>(null)
  const [wiki, setWiki] = useState<WikipediaMaking | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setRx(null)
    setMade(null)
    setWiki(null)
    setError(null)
    analysisApi.reactions(mol.smiles)
      .then((d) => live && setRx(d))
      .catch((e: Error) => live && setError(e.message))
    // How the molecule is made (PubChem, Wikipedia) is extra; the card works without it.
    analysisApi.manufacture(mol.smiles)
      .then((d) => live && setMade(d))
      .catch(() => live && setMade(null))
    analysisApi.wikipedia(mol.smiles)
      .then((d) => live && setWiki(d))
      .catch(() => live && setWiki(null))
    return () => { live = false }
  }, [mol.smiles])

  return (
    <section className="card">
      <header className="card-head">
        <h2>Reactions</h2>
      </header>
      {error && <p className="warn">{error}</p>}
      {!error && !rx && <p className="muted small">Loading…</p>}
      {rx && <RecordedTab data={rx} made={made} wiki={wiki} onOpen={onOpen} onHighlight={onHighlight} />}
    </section>
  )
}

function RecordedTab({ data, made, wiki, onOpen, onHighlight }: {
  data: RecordedReactions
  made: Manufacture | null
  wiki: WikipediaMaking | null
  onOpen: Props['onOpen']
  onHighlight: Props['onHighlight']
}) {
  if (!data.available) {
    return <p className="muted">The reaction index is not installed on this server.</p>
  }
  const textbookUses = data.textbook_uses ?? []
  const textbookMakes = data.textbook_makes ?? []
  return (
    <div className="bonding-body">
      {data.uses.length === 0 && data.makes.length === 0 && textbookUses.length === 0 && textbookMakes.length === 0 && (
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
        <p className="muted small">Reactions of every stereoisomer of this structure are shown together. Rows marked "other stereoisomer" have an example recorded for a different stereoisomer, or without stereochemistry.</p>
      )}
      <Section title="Used in" empty={textbookUses.length ? '' : 'No recorded reactions use this molecule as a starting material.'} items={data.uses} direction="uses" onOpen={onOpen} onHighlight={onHighlight} />
      {textbookUses.length > 0 && (
        <Section title="Used in, textbook routes" empty="" items={textbookUses} direction="uses" kind="textbook" onOpen={onOpen} onHighlight={onHighlight} />
      )}
      {textbookMakes.length > 0 && (
        <Section title="Made by, textbook routes" empty="" items={textbookMakes} direction="makes" kind="textbook" onOpen={onOpen} onHighlight={onHighlight} />
      )}
      <Section title="Made by" empty={made?.methods.length || wiki?.paragraphs.length || textbookMakes.length ? '' : 'No recorded reactions make this molecule.'} items={data.makes} direction="makes" onOpen={onOpen} onHighlight={onHighlight} />
      {made && made.methods.length > 0 && <Methods data={made} onOpen={onOpen} />}
      {wiki && wiki.paragraphs.length > 0 && <Wikipedia data={wiki} onOpen={onOpen} />}
      {data.enzyme_uses.length > 0 && (
        <Section title="Used in by enzymes" empty="" items={data.enzyme_uses} direction="uses" kind="enzyme" onOpen={onOpen} onHighlight={onHighlight} />
      )}
      {data.enzyme_makes.length > 0 && (
        <Section title="Made by enzymes" empty="" items={data.enzyme_makes} direction="makes" kind="enzyme" onOpen={onOpen} onHighlight={onHighlight} />
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

const SEEN_IN = { recorded: 'recorded reaction', enzyme: 'enzyme reaction', textbook: 'Wikipedia route' }

function Section({ title, empty, items, direction, kind = 'recorded', onOpen, onHighlight }: {
  title: string
  empty: string
  items: RecordedReaction[]
  direction: 'uses' | 'makes'
  kind?: keyof typeof SEEN_IN
  onOpen: Props['onOpen']
  onHighlight: Props['onHighlight']
}) {
  return (
    <>
      <h3>{title}</h3>
      {items.length === 0 && empty && <p className="muted small">{empty}</p>}
      <ol className="rxn-rows recorded">
        {items.map((r) => {
          const others = direction === 'uses' ? r.products.slice(0, 1) : r.reactants
          return (
            <li key={r.label} className="rxn-row recorded" onMouseEnter={() => r.atoms.length && onHighlight(r.atoms, '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
              <div className="rxn-info">
                <b>{r.label}</b>
                <span className="muted small">
                  seen in {r.count} {SEEN_IN[kind]}{r.count === 1 ? '' : 's'}
                  {r.other_stereo && ', other stereoisomer'}
                </span>
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

/** Text with the compounds it names turned into buttons that open them. */
function LinkedText({ text, compounds, onOpen }: { text: string; compounds: LinkedCompound[]; onOpen: Props['onOpen'] }) {
  const parts: ReactNode[] = []
  let at = 0
  for (const c of [...compounds].sort((a, b) => a.start - b.start)) {
    if (c.start < at) continue
    parts.push(text.slice(at, c.start))
    parts.push(
      <button key={c.start} type="button" className="link" title={`Open ${c.name}`} onClick={() => onOpen(c.smiles || c.name)}>
        {text.slice(c.start, c.start + c.length)}
      </button>,
    )
    at = c.start + c.length
  }
  parts.push(text.slice(at))
  return <>{parts}</>
}

function Methods({ data, onOpen }: { data: Manufacture; onOpen: Props['onOpen'] }) {
  return (
    <div className="rxn-methods">
      <h4>Manufacturing and preparation methods</h4>
      {data.stereo_ignored && (
        <p className="muted small">These describe the compound without its stereochemistry, usually made as a mixture of stereoisomers.</p>
      )}
      <ul className="lit-list">
        {data.methods.map((m, i) => (
          <li key={i}>
            <span className="small"><LinkedText text={m.text} compounds={m.compounds} onOpen={onOpen} /></span>
            {m.reference && <span className="muted small">{m.reference}</span>}
          </li>
        ))}
      </ul>
      <p className="muted small">
        From <a href={data.url} target="_blank" rel="noopener noreferrer">PubChem</a>, which takes them from the{' '}
        <a href={data.source_url} target="_blank" rel="noopener noreferrer">Hazardous Substances Data Bank</a> of the U.S. National Library of Medicine.
        Named compounds open here.
      </p>
    </div>
  )
}

function Wikipedia({ data, onOpen }: { data: WikipediaMaking; onOpen: Props['onOpen'] }) {
  const images = (after: number) => data.images.filter((im) => im.after === after).map((im) => (
    <figure key={im.file} className="wiki-scheme">
      <a href={im.page || data.url} target="_blank" rel="noopener noreferrer">
        <img src={im.src} alt={`Reaction scheme from the Wikipedia article ${data.title}`} loading="lazy" />
      </a>
      <figcaption className="muted small">
        {[im.author, im.licence].filter(Boolean).join(', ')}{im.author || im.licence ? ', ' : ''}
        <a href={im.page} target="_blank" rel="noopener noreferrer">Wikimedia Commons</a>
      </figcaption>
    </figure>
  ))
  return (
    <div className="rxn-methods">
      <h4>From Wikipedia, {data.section}</h4>
      {data.stereo_ignored && (
        <p className="muted small">The article covers the compound without this stereochemistry.</p>
      )}
      {images(0)}
      {data.paragraphs.map((p, i) => (
        <div key={i}>
          <p className="small wiki-text"><LinkedText text={p.text} compounds={p.compounds} onOpen={onOpen} /></p>
          {images(i + 1)}
        </div>
      ))}
      <p className="muted small">
        Text from the Wikipedia article <a href={data.url} target="_blank" rel="noopener noreferrer">{data.title}</a>,{' '}
        <a href={data.licence_url} target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>. Named compounds open here.
      </p>
    </div>
  )
}
