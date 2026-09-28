import { Fragment, useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { ChemRxiv, Journals, Literature as LiteratureData, Patents } from './types'

type Tab = 'chemrxiv' | 'journals' | 'patents'
const TABS: { id: Tab; label: string }[] = [
  { id: 'chemrxiv', label: 'ChemRxiv' },
  { id: 'journals', label: 'Journals' },
  { id: 'patents', label: 'Patents' },
]
const SHOWN = 5

/** Preprints, journal articles and patents about the molecule. */
export function Literature({ mol }: { mol: Molecule }) {
  const [lit, setLit] = useState<LiteratureData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab | null>(null)

  useEffect(() => {
    let live = true
    setLit(null)
    setError(null)
    setTab(null)
    // A typed name is a fallback search term when PubChem has no name for the structure.
    const name = ['iupac', 'pubchem', 'cactus'].includes(mol.source) ? mol.input_text : ''
    analysisApi.literature(mol.smiles, name)
      .then((d) => live && setLit(d))
      .catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [mol.smiles, mol.source, mol.input_text])

  // Open the first source that found something, until the user picks one.
  const shown: Tab = tab ?? TABS.find((t) => lit && lit[t.id].items.length > 0)?.id ?? 'chemrxiv'

  return (
    <section className="card">
      <header className="card-head">
        <h2>Literature</h2>
        {lit && (
          <div className="toolbar" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} type="button" role="tab" aria-selected={shown === t.id} className={shown === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>
                {t.label} <span className="muted small">{lit[t.id].items.length}</span>
              </button>
            ))}
          </div>
        )}
      </header>
      {error && <p className="warn">{error}</p>}
      {!error && !lit && <p className="muted small">Loading…</p>}
      {lit && shown === 'chemrxiv' && <ChemRxivList key={mol.smiles} data={lit.chemrxiv} />}
      {lit && shown === 'journals' && <JournalList key={mol.smiles} data={lit.journals} />}
      {lit && shown === 'patents' && <PatentList key={mol.smiles} data={lit.patents} />}
    </section>
  )
}

function Highlight({ text, term }: { text: string; term: string }) {
  if (!term) return <>{text}</>
  const parts = text.split(new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'i'))
  return <>{parts.map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : <Fragment key={i}>{p}</Fragment>))}</>
}

function MoreButton({ total, open, onToggle }: { total: number; open: boolean; onToggle: () => void }) {
  if (total <= SHOWN) return null
  return (
    <button type="button" className="link small" onClick={onToggle}>
      {open ? 'Show fewer' : `Show ${total - SHOWN} more`}
    </button>
  )
}

function ChemRxivList({ data }: { data: ChemRxiv }) {
  if (!data.available) return <p className="muted">{data.reason}</p>
  return (
    <div className="bonding-body">
      {data.match === 'fulltext' && data.items.length > 0 && (
        <p className="muted small">No ChemRxiv title or abstract names “{data.query}”, so these preprints are ones that mention it in the text.</p>
      )}
      {data.items.length === 0 ? (
        <p className="muted">No ChemRxiv preprints found for “{data.query}”.</p>
      ) : (
        <ol className="lit-list">
          {data.items.map((p) => (
            <li key={p.doi}>
              <a href={p.url} target="_blank" rel="noopener noreferrer"><b>{p.title}</b></a>
              <span className="muted small">
                {[p.authors, p.date, p.cited_by != null ? `cited ${p.cited_by}×` : ''].filter(Boolean).join(' · ')}
              </span>
              {p.snippet && <span className="small lit-snippet"><Highlight text={p.snippet} term={data.query} /></span>}
            </li>
          ))}
        </ol>
      )}
      <p className="muted small">Searched ChemRxiv for “{data.query}”{data.source ? ` via ${data.source}` : ''}. Preprints are not peer reviewed. Links open the ChemRxiv page.</p>
    </div>
  )
}

function JournalList({ data }: { data: Journals }) {
  const [open, setOpen] = useState(false)
  if (!data.available) return <p className="muted">{data.reason}</p>
  const items = open ? data.items : data.items.slice(0, SHOWN)
  return (
    <div className="bonding-body">
      {data.items.length === 0 ? (
        <p className="muted">No journal articles found{data.query ? ` for “${data.query}”` : ''}.</p>
      ) : (
        <ol className="lit-list">
          {items.map((a) => (
            <li key={a.url}>
              <a href={a.url} target="_blank" rel="noopener noreferrer"><b>{a.title}</b></a>
              <span className="muted small">
                {[a.authors, a.journal, a.year, `cited ${a.cited_by}×`, a.type === 'review' ? 'review' : ''].filter(Boolean).join(' · ')}
              </span>
            </li>
          ))}
        </ol>
      )}
      <MoreButton total={data.items.length} open={open} onToggle={() => setOpen(!open)} />
      <p className="muted small">
        {data.match === 'pubchem'
          ? `Articles PubChem links to this exact structure (${data.total.toLocaleString()} in all), ranked by citations, with recent articles and titles that name the molecule first.`
          : `PubChem links no articles to this structure, so these are articles whose title names “${data.query}”.`}
        {' '}Details from <a href="https://openalex.org" target="_blank" rel="noopener noreferrer">OpenAlex</a>.
      </p>
    </div>
  )
}

function PatentList({ data }: { data: Patents }) {
  const [open, setOpen] = useState(false)
  const items = open ? data.items : data.items.slice(0, SHOWN)
  return (
    <div className="bonding-body">
      {data.items.length === 0 ? (
        <p className="muted">No patent in the reaction records makes or uses this molecule.</p>
      ) : (
        <ol className="lit-list">
          {items.map((p) => (
            <li key={p.number}>
              <a href={p.url} target="_blank" rel="noopener noreferrer"><b>{p.title || p.number}</b></a>
              <span className="muted small">
                {[p.title ? p.number : '', p.date || p.year, p.assignee].filter(Boolean).join(' · ')}
              </span>
              <span className="small">
                {p.reactions.map((r) => `${r.direction === 'uses' ? 'Uses it' : 'Makes it'} (${r.label})`).join(', ')}
              </span>
            </li>
          ))}
        </ol>
      )}
      <MoreButton total={data.items.length} open={open} onToggle={() => setOpen(!open)} />
      <p className="muted small">
        US patents whose worked examples make or use this molecule, from the reaction records. Titles from PubChem.
        {data.pubchem_url && <> <a href={data.pubchem_url} target="_blank" rel="noopener noreferrer">PubChem lists more patents that mention it</a>.</>}
      </p>
    </div>
  )
}
