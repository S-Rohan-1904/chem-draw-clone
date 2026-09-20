import { useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { IsotopeLabel, IsotopeResult } from './types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

const NAMES: Record<string, string> = { '2H': 'D (2H)', '3H': 'T (3H)', '13C': '13C', '14C': '14C', '15N': '15N', '17O': '17O', '18O': '18O', '34S': '34S', '37Cl': '37Cl', '81Br': '81Br' }

export function Isotopes({ mol, onHighlight }: Props) {
  const [open, setOpen] = useState(false)
  const [labels, setLabels] = useState<IsotopeLabel[]>([])
  const [data, setData] = useState<IsotopeResult | null>(null)
  const [atom, setAtom] = useState(0)
  const [code, setCode] = useState('2H')
  const [count, setCount] = useState(1)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLabels([])
    setData(null)
    setOpen(false)
    setError(null)
  }, [mol.smiles])

  useEffect(() => {
    if (!open) return
    analysisApi
      .isotopes(mol.smiles, labels)
      .then((r) => {
        setData(r)
        setError(null)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not apply the labels'))
  }, [open, labels, mol.smiles])

  const sym = (i: number) => `${mol.atoms?.[i]?.symbol ?? ''}${i + 1}`
  const options = data?.options ?? []
  const current = options.find((o) => o.atom_idx === atom) ?? options[0]

  useEffect(() => {
    if (!current) return
    if (!current.codes.includes(code)) setCode(current.codes[0])
    if (current.hs && count > current.hs) setCount(current.hs)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current])

  const add = () => {
    if (!current) return
    const isH = code === '2H' || code === '3H'
    setLabels((ls) => [...ls.filter((l) => !(l.atom_idx === current.atom_idx && ((l.isotope === '2H' || l.isotope === '3H') === isH))), { atom_idx: current.atom_idx, isotope: code, count: isH ? count : 1 }])
  }

  if (!open) {
    return (
      <section className="card">
        <header className="card-head">
          <h2>Isotope labels</h2>
          <button type="button" onClick={() => setOpen(true)}>Label atoms</button>
        </header>
        <p className="muted small">Replace atoms or hydrogens with heavier isotopes and see the exact mass shift.</p>
      </section>
    )
  }

  return (
    <section className="card">
      <header className="card-head">
        <h2>Isotope labels</h2>
        {data && <span className="tag">{data.nominal_shift > 0 ? `M + ${data.nominal_shift}` : 'no shift'}</span>}
      </header>
      <div className="bonding-split">
        <div>
          {data && <div className="svg-wrap bonding-svg" dangerouslySetInnerHTML={{ __html: data.svg }} />}
        </div>
        <div>
          {options.length > 0 && (
            <div className="toolbar">
              <label className="check">
                Atom
                <select value={current?.atom_idx ?? 0} onChange={(e) => setAtom(Number(e.target.value))} aria-label="Atom" onMouseEnter={() => current && onHighlight([current.atom_idx], '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
                  {options.map((o) => <option key={o.atom_idx} value={o.atom_idx}>{sym(o.atom_idx)}{o.hs ? ` (${o.hs} H)` : ''}</option>)}
                </select>
              </label>
              <label className="check">
                Isotope
                <select value={code} onChange={(e) => setCode(e.target.value)} aria-label="Isotope">
                  {(current?.codes ?? []).map((c) => <option key={c} value={c}>{NAMES[c] ?? c}</option>)}
                </select>
              </label>
              {(code === '2H' || code === '3H') && current && current.hs > 1 && (
                <label className="check">
                  How many
                  <select value={count} onChange={(e) => setCount(Number(e.target.value))} aria-label="How many hydrogens">
                    {Array.from({ length: current.hs }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
              )}
              <button type="button" className="primary" onClick={add}>Add label</button>
            </div>
          )}
          {error && <p className="error small">{error}</p>}
          {labels.length > 0 && (
            <ul className="bonding-list">
              {(data?.applied ?? []).map((a, i) => (
                <li key={i} onMouseEnter={() => onHighlight([a.atom_idx], '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
                  {a.text} <button type="button" className="link" onClick={() => setLabels((ls) => ls.filter((_, k) => k !== i))}>remove</button>
                </li>
              ))}
            </ul>
          )}
          {data && (
            <dl className="props">
              <dt>Labelled formula</dt><dd>{data.formula}</dd>
              <dt>Exact mass</dt><dd>{data.exact_mass.toFixed(4)} (unlabelled {data.base_mass.toFixed(4)})</dd>
              <dt>Mass shift</dt><dd>{data.shift > 0 ? '+' : ''}{data.shift.toFixed(4)} Da</dd>
              <dt>SMILES</dt><dd><code>{data.smiles}</code></dd>
            </dl>
          )}
          <div className="toolbar">
            <button type="button" onClick={() => setLabels([])} disabled={labels.length === 0}>Clear labels</button>
            <button type="button" onClick={() => setOpen(false)}>Close</button>
          </div>
          <p className="muted small">The molecular ion moves up by the nominal shift in a mass spectrum. Deuterium is silent in 1H NMR, so a labelled position loses its signal.</p>
        </div>
      </div>
    </section>
  )
}
