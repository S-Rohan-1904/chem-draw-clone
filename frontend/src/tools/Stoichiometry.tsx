import { useEffect, useMemo, useState } from 'react'
import type { ReactionResult } from '../types'

interface Props {
  rxn: ReactionResult
}

interface Row {
  coeff: number
  grams: string // user-entered mass, '' = unknown
}

const mmol = (g: string, mw: number) => (g.trim() === '' || Number.isNaN(Number(g)) ? null : (Number(g) / mw) * 1000)

/** Moles, equivalents, limiting reagent and theoretical yield for a reaction. */
export function Stoichiometry({ rxn }: Props) {
  const key = rxn.svg
  const [open, setOpen] = useState(false)
  const [reac, setReac] = useState<Row[]>([])
  const [prod, setProd] = useState<number[]>([])
  const [actual, setActual] = useState<string[]>([])

  useEffect(() => {
    setReac(rxn.reactants.map(() => ({ coeff: 1, grams: '' })))
    setProd(rxn.products.map(() => 1))
    setActual(rxn.products.map(() => ''))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const calc = useMemo(() => {
    const moles = reac.map((r, i) => {
      const m = mmol(r.grams, rxn.reactants[i]?.mw ?? 1)
      return m === null ? null : m / (r.coeff || 1) // "extent" each reagent could support
    })
    const known = moles.map((m, i) => [m, i] as const).filter((x): x is readonly [number, number] => x[0] !== null)
    if (known.length === 0) return null
    const [extent, limiting] = known.reduce((a, b) => (b[0] < a[0] ? b : a))
    return { extent, limiting, moles }
  }, [reac, rxn.reactants])

  if (rxn.reactants.length === 0 || rxn.reactants.some((r) => !r.mw)) return null

  const setRow = (i: number, patch: Partial<Row>) => setReac((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  return (
    <div className="stoich">
      <button type="button" className="link small" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? 'Hide' : 'Show'} stoichiometry</button>
      {open && reac.length === rxn.reactants.length && (
        <>
          <table className="bonding-table stoich-table">
            <thead>
              <tr><th></th><th>Coeff.</th><th>Formula</th><th>MW</th><th>Mass (g)</th><th>mmol</th><th>Equiv.</th></tr>
            </thead>
            <tbody>
              {rxn.reactants.map((r, i) => {
                const m = mmol(reac[i].grams, r.mw)
                const eq = calc && m !== null ? m / (reac[i].coeff || 1) / calc.extent : null
                return (
                  <tr key={i} className={calc?.limiting === i ? 'limiting' : ''}>
                    <td><code>{r.smiles}</code>{calc?.limiting === i && <span className="tag tag-warn">limiting</span>}</td>
                    <td><input type="number" min={1} step={1} value={reac[i].coeff} onChange={(e) => setRow(i, { coeff: Math.max(1, Number(e.target.value) || 1) })} aria-label="Coefficient" className="stoich-num" /></td>
                    <td>{r.formula}</td>
                    <td>{r.mw.toFixed(2)}</td>
                    <td><input type="number" min={0} step="any" value={reac[i].grams} onChange={(e) => setRow(i, { grams: e.target.value })} placeholder="?" aria-label="Mass in grams" className="stoich-num" /></td>
                    <td>{m === null ? (calc ? (calc.extent * (reac[i].coeff || 1)).toFixed(2) + ' needed' : '') : m.toFixed(2)}</td>
                    <td>{eq === null ? '' : eq.toFixed(2)}</td>
                  </tr>
                )
              })}
              {rxn.products.map((p, i) => {
                const theo = calc ? (calc.extent * (prod[i] || 1) * p.mw) / 1000 : null
                const got = actual[i]?.trim() === '' ? null : Number(actual[i])
                const pct = theo && got !== null && !Number.isNaN(got) ? (100 * got) / theo : null
                return (
                  <tr key={`p${i}`} className="product">
                    <td><code>{p.smiles}</code><span className="tag">product</span></td>
                    <td><input type="number" min={1} step={1} value={prod[i] ?? 1} onChange={(e) => setProd((c) => c.map((v, j) => (j === i ? Math.max(1, Number(e.target.value) || 1) : v)))} aria-label="Coefficient" className="stoich-num" /></td>
                    <td>{p.formula}</td>
                    <td>{p.mw.toFixed(2)}</td>
                    <td>
                      {theo !== null ? <span title="theoretical yield">{theo.toFixed(3)} theo.</span> : ''}
                      <input type="number" min={0} step="any" value={actual[i] ?? ''} onChange={(e) => setActual((a) => a.map((v, j) => (j === i ? e.target.value : v)))} placeholder="actual" aria-label="Actual mass in grams" className="stoich-num" />
                    </td>
                    <td>{theo !== null ? (calc!.extent * (prod[i] || 1)).toFixed(2) : ''}</td>
                    <td>{pct !== null ? <b>{pct.toFixed(1)}% yield</b> : ''}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="muted small">Enter the mass of at least one reactant. Coefficients come from you: the reaction SMILES carries none. The limiting reagent is the one that supports the smallest number of reaction equivalents; equivalents and theoretical yield are relative to it.</p>
        </>
      )}
    </div>
  )
}
