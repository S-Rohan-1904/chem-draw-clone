import { useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { PredictedReaction, RetroRoute } from './types'

interface Props {
  mol: Molecule
  onOpen: (smiles: string) => void
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

export function Reactions({ mol, onOpen, onHighlight }: Props) {
  const [tab, setTab] = useState<'forward' | 'retro'>('forward')
  const [forward, setForward] = useState<PredictedReaction[] | null>(null)
  const [retro, setRetro] = useState<RetroRoute[] | null>(null)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    setForward(null)
    setRetro(null)
    setFilter('all')
    analysisApi.products(mol.smiles).then((r) => setForward(r.reactions)).catch(() => setForward([]))
    analysisApi.retro(mol.smiles).then((r) => setRetro(r.routes)).catch(() => setRetro([]))
  }, [mol.smiles])

  if (forward === null || retro === null) return null
  if (forward.length === 0 && retro.length === 0) return null
  const categories = Array.from(new Set(forward.map((r) => r.category)))
  const shown = filter === 'all' ? forward : forward.filter((r) => r.category === filter)

  return (
    <section className="card">
      <header className="card-head">
        <h2>Reactions</h2>
        <div className="toolbar">
          <button type="button" className={tab === 'forward' ? 'active' : ''} onClick={() => setTab('forward')}>What can it make ({forward.length})</button>
          <button type="button" className={tab === 'retro' ? 'active' : ''} onClick={() => setTab('retro')}>Where can it come from ({retro.length})</button>
        </div>
      </header>

      {tab === 'forward' && (
        <div className="bonding-body">
          {forward.length === 0 && <p className="muted">No textbook reaction applies to this molecule.</p>}
          {categories.length > 1 && (
            <div className="toolbar">
              <button type="button" className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>all</button>
              {categories.map((c) => <button key={c} type="button" className={filter === c ? 'active' : ''} onClick={() => setFilter(c)}>{c}</button>)}
            </div>
          )}
          <ul className="rxn-rows">
            {shown.map((r) => (
              <li key={r.name} className="rxn-row" onMouseEnter={() => r.products[0]?.atoms.length && onHighlight(r.products[0].atoms, '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
                <div className="rxn-info">
                  <b>{r.name}</b>
                  <span className="muted small">{r.reagents}</span>
                  {r.note && <span className="small">{r.note}</span>}
                </div>
                <div className="rxn-products">
                  {r.products.map((p, i) => (
                    <div key={i} className="rxn-product">
                      {p.svgs.map((svg, k) => (
                        <button key={k} type="button" className="rxn-thumb" title={`Open ${p.smiles[k]}`} onClick={() => onOpen(p.smiles[k])}>
                          <div dangerouslySetInnerHTML={{ __html: svg }} />
                        </button>
                      ))}
                      {p.why && <span className="muted small">{p.why}</span>}
                    </div>
                  ))}
                </div>
              </li>
            ))}
          </ul>
          <p className="muted small">Select a product to load it and continue. Regiochemistry follows the textbook rule named for each reaction; stereochemistry of the products is not assigned.</p>
        </div>
      )}

      {tab === 'retro' && (
        <div className="bonding-body">
          {retro.length === 0 && <p className="muted">No disconnection found.</p>}
          <ul className="rxn-rows">
            {retro.map((r) => (
              <li key={r.name + r.target_group} className="rxn-row" onMouseEnter={() => r.precursors[0]?.atoms.length && onHighlight(r.precursors[0].atoms, '#7c3aed')} onMouseLeave={() => onHighlight(null)}>
                <div className="rxn-info">
                  <b>{r.name}</b>
                  <span className="muted small">makes the {r.target_group}: {r.reagents}</span>
                  {r.note && <span className="small">{r.note}</span>}
                </div>
                <div className="rxn-products">
                  {r.precursors.map((p, i) => (
                    <div key={i} className="rxn-product">
                      {p.svgs.map((svg, k) => (
                        <button key={k} type="button" className="rxn-thumb" title={`Open ${p.smiles[k]}`} onClick={() => onOpen(p.smiles[k])}>
                          <div dangerouslySetInnerHTML={{ __html: svg }} />
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </li>
            ))}
          </ul>
          <p className="muted small">One step back. Select a precursor to load it and take the next step back.</p>
        </div>
      )}
    </section>
  )
}
