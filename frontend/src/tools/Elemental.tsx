import { useEffect, useState } from 'react'
import { toolsApi } from './api'
import type { Elemental as ElementalData } from './types'

/** Mass-percent table, loaded when opened. */
export function Elemental({ smiles }: { smiles: string }) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<ElementalData | null>(null)

  useEffect(() => {
    setData(null)
    setOpen(false)
  }, [smiles])

  useEffect(() => {
    if (!open || data) return
    toolsApi.elemental(smiles).then(setData).catch(() => setData(null))
  }, [open, data, smiles])

  return (
    <div className="elemental">
      <button type="button" className="link small" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? 'Hide' : 'Show'} elemental analysis
      </button>
      {open && data && (
        <table className="bonding-table elemental-table">
          <thead>
            <tr><th>Element</th><th>Atoms</th><th>Mass (g/mol)</th><th>%</th></tr>
          </thead>
          <tbody>
            {data.elements.map((e) => (
              <tr key={e.symbol}>
                <td>{e.symbol}</td>
                <td>{e.count}</td>
                <td>{e.mass.toFixed(3)}</td>
                <td><span className="frac-bar" aria-hidden="true"><span style={{ width: `${e.percent}%` }} /></span>{e.percent.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr><td>{data.formula}</td><td>{data.elements.reduce((n, e) => n + e.count, 0)}</td><td>{data.mw.toFixed(3)}</td><td>100</td></tr>
          </tfoot>
        </table>
      )}
      {open && !data && <p className="muted small">Calculating...</p>}
    </div>
  )
}
