import { Fragment, useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { ChemRxiv, JournalArticle, JournalMatch, Journals, Literature as LiteratureData, Patents } from './types'

type Tab = 'chemrxiv' | 'journals' | 'patents'
const TABS: { id: Tab; label: string }[] = [
  { id: 'chemrxiv', label: 'ChemRxiv' },
  { id: 'journals', label: 'Journals' },
  { id: 'patents', label: 'Patents' },
]
const SHOWN = 5
const RETRY_MS = 12000

function isPending(d: LiteratureData): boolean {
  return !!d.chemrxiv.pending || d.patents.pending || d.patents.surechembl.pending
    || Object.values(d.journals.sources).some((s) => s.pending)
}

function Pending({ names }: { names: string[] }) {
  if (names.length === 0) return null
  return <p className="muted small">Still searching {names.join(' and ')}: the list fills in when {names.length > 1 ? 'they answer' : 'it answers'}.</p>
}

/** Preprints, journal articles and patents about the molecule. */
export function Literature({ mol }: { mol: Molecule }) {
  const [lit, setLit] = useState<LiteratureData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab | null>(null)

  useEffect(() => {
    let live = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let shown = false
    setLit(null)
    setError(null)
    setTab(null)
    // A typed name is a fallback search term when PubChem has no name for the structure.
    const name = ['iupac', 'pubchem', 'cactus'].includes(mol.source) ? mol.input_text : ''
    const load = (tries: number) => analysisApi.literature(mol.smiles, name)
      .then((d) => {
        if (!live) return
        shown = true
        setLit(d)
        // Slow sources finish on the server after the card answers; ask again for them.
        if (tries > 0 && isPending(d)) timer = setTimeout(() => void load(tries - 1), RETRY_MS)
      })
      .catch((e: Error) => live && !shown && setError(e.message)) // a failed retry keeps what is shown
    void load(3)
    return () => { live = false; clearTimeout(timer) }
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
  if (data.pending) return <Pending names={['ChemRxiv']} />
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
      <p className="muted small">Searched ChemRxiv for “{data.query}”{data.source ? ` via ${data.source}` : ''}. Preprints are free to read but not peer reviewed. Links open the ChemRxiv page.</p>
    </div>
  )
}

const MATCH_LABEL: Record<JournalMatch, string> = {
  structure: 'exact structure',
  title: 'named in title',
  abstract: 'named in abstract',
  text: 'mentioned in text',
}
type Filter = 'about' | 'making' | 'review' | 'free'
const FILTERS: { id: Filter; label: string; test: (a: JournalArticle) => boolean }[] = [
  { id: 'about', label: 'About it', test: (a) => a.about },
  { id: 'making', label: 'Making', test: (a) => a.making },
  { id: 'review', label: 'Reviews', test: (a) => a.type === 'review' },
  { id: 'free', label: 'Free full text', test: (a) => !!a.oa_url },
]
type Sort = 'relevance' | 'newest' | 'cited'

function JournalList({ data }: { data: Journals }) {
  const [open, setOpen] = useState(false)
  const [filters, setFilters] = useState<Filter[]>([])
  const [sort, setSort] = useState<Sort>('relevance')
  if (!data.available) return <p className="muted">{data.reason}</p>
  const kept = data.items.filter((a) => filters.every((f) => FILTERS.find((x) => x.id === f)!.test(a)))
  const sorted = sort === 'relevance' ? kept
    : [...kept].sort((a, b) => (sort === 'newest' ? (b.year ?? 0) - (a.year ?? 0) : b.cited_by - a.cited_by))
  const items = open ? sorted : sorted.slice(0, SHOWN)
  const toggle = (f: Filter) => setFilters(filters.includes(f) ? filters.filter((x) => x !== f) : [...filters, f])
  return (
    <div className="bonding-body">
      {data.items.length > 0 && (
        <div className="lit-controls">
          {FILTERS.map((f) => {
            const n = data.items.filter(f.test).length
            return (
              <button key={f.id} type="button" className={`chip chip-group${filters.includes(f.id) ? ' active' : ''}`} aria-pressed={filters.includes(f.id)}
                disabled={n === 0 && !filters.includes(f.id)} onClick={() => toggle(f.id)}>
                {f.label} <span className="count">{n}</span>
              </button>
            )
          })}
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sort articles">
            <option value="relevance">Most relevant</option>
            <option value="newest">Newest</option>
            <option value="cited">Most cited</option>
          </select>
        </div>
      )}
      <Pending names={Object.entries(data.sources).filter(([, s]) => s.pending).map(([n]) => n)} />
      {data.items.length === 0 ? (
        <p className="muted">No journal articles found{data.query ? ` for “${data.query}”` : ''}.</p>
      ) : sorted.length === 0 ? (
        <p className="muted">No article matches every filter.</p>
      ) : (
        <ol className="lit-list">
          {items.map((a) => (
            <li key={a.doi || a.pmid || a.url}>
              <a href={a.url} target="_blank" rel="noopener noreferrer"><b>{a.title}</b></a>
              <span className="muted small">
                {[a.authors, a.journal, a.year, a.cited_by ? `cited ${a.cited_by}×` : '', a.type === 'review' ? 'review' : ''].filter(Boolean).join(' · ')}
              </span>
              <span className="lit-tags small">
                <span className={`tag lit-match-${a.match}`}>{MATCH_LABEL[a.match]}</span>
                <span className="tag">{a.sources.join(' + ')}</span>
                {a.ord && <span className="tag">{a.ord.reactions} reaction{a.ord.reactions === 1 ? '' : 's'} in ORD ({a.ord.roles.join(', ')})</span>}
                {a.oa_url && <a className="tag tag-ok" href={a.oa_url} target="_blank" rel="noopener noreferrer">Free full text</a>}
              </span>
              {a.snippet && a.match === 'abstract' && <span className="small lit-snippet"><Highlight text={a.snippet} term={data.query} /></span>}
            </li>
          ))}
        </ol>
      )}
      <MoreButton total={sorted.length} open={open} onToggle={() => setOpen(!open)} />
      <p className="muted small">
        Articles linked to this exact structure by PubMed (through PubChem), ChEMBL and the Open Reaction Database, chemistry
        journal articles that name it (OpenAlex), and articles that mention it in the text (Europe PMC). Each article is listed
        once, with every source that found it.
      </p>
      <p className="muted small lit-sources">
        {Object.entries(data.sources).map(([name, s]) => (
          <span key={name}>
            {name}: {s.pending ? 'searching…' : !s.available ? <span className="hint-bad">not reachable</span> : s.count}
            {s.stale ? ' (earlier search, not reachable now)' : ''}
          </span>
        ))}
      </p>
    </div>
  )
}

function PatentList({ data }: { data: Patents }) {
  const [open, setOpen] = useState(false)
  const items = open ? data.items : data.items.slice(0, SHOWN)
  const sure = data.surechembl
  return (
    <div className="bonding-body">
      <Pending names={[data.pending ? 'the reaction records' : '', sure.pending ? 'SureChEMBL' : ''].filter(Boolean)} />
      {data.items.length === 0 ? (
        <p className="muted">No patent found that makes, uses or contains this molecule.</p>
      ) : (
        <ol className="lit-list">
          {items.map((p) => (
            <li key={p.number}>
              <a href={p.url} target="_blank" rel="noopener noreferrer"><b>{p.title || p.number}</b></a>
              <span className="muted small">
                {[p.title ? p.number : '', p.date || p.year, p.assignee].filter(Boolean).join(' · ')}
              </span>
              <span className="lit-tags small">
                <span className="tag">{p.sources.join(' + ')}</span>
                {p.about && <span className="tag">names it</span>}
                {p.making && <span className="tag">making</span>}
              </span>
              {p.reactions.length > 0 && (
                <span className="small">
                  {p.reactions.map((r) => `${r.direction === 'uses' ? 'Uses it' : 'Makes it'} (${r.label})`).join(', ')}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
      <MoreButton total={data.items.length} open={open} onToggle={() => setOpen(!open)} />
      <p className="muted small">
        US patents whose worked examples make or use this molecule (reaction records, to 2016), and patents of every year and
        country that contain it (SureChEMBL{sure.total ? `, ${sure.total.toLocaleString()} in all, the most relevant of the newest 200 shown` : ''}).
        Patents that name the molecule or are about making something come first.
        {!sure.available && <> <span className="hint-bad">SureChEMBL is not reachable right now.</span></>}
        {data.pubchem_url && <> <a href={data.pubchem_url} target="_blank" rel="noopener noreferrer">PubChem lists more patents that mention it</a>.</>}
      </p>
    </div>
  )
}
