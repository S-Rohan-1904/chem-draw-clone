import { useEffect, useState } from 'react'
import { ApiError } from '../api'
import { Structure3D } from '../components/Structure3D'
import type { Molecule } from '../types'
import { toolsApi } from './api'
import type { ConformerSet, Minimised } from './types'

interface Props {
  mol: Molecule
}

/** MMFF conformer ensemble and single-point minimisation of the shown model. */
export function Conformers({ mol }: Props) {
  const [set, setSet] = useState<ConformerSet | null>(null)
  const [sel, setSel] = useState(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [mini, setMini] = useState<Minimised | null>(null)
  const [miniBusy, setMiniBusy] = useState(false)

  useEffect(() => {
    setSet(null)
    setSel(0)
    setErr(null)
    setMini(null)
  }, [mol.smiles])

  const run = () => {
    setBusy(true)
    setErr(null)
    toolsApi.conformers(mol.smiles, 8)
      .then((s) => { setSet(s); setSel(0) })
      .catch((e) => setErr(e instanceof ApiError ? e.message : 'Conformer search failed.'))
      .finally(() => setBusy(false))
  }

  const minimise = () => {
    setMiniBusy(true)
    setErr(null)
    toolsApi.minimise(mol.smiles)
      .then(setMini)
      .catch((e) => setErr(e instanceof ApiError ? e.message : 'Minimisation failed.'))
      .finally(() => setMiniBusy(false))
  }

  if (mol.properties.heavy_atoms > 40) return null
  const current = set?.conformers[sel]

  return (
    <section className="card">
      <header className="card-head">
        <h2>Conformers and energy</h2>
        <div className="toolbar">
          <button type="button" onClick={minimise} disabled={miniBusy} title="Re-minimise the shown 3D model with MMFF94 and report its steric energy">
            {miniBusy ? 'Minimising...' : 'Minimise model'}
          </button>
          <button type="button" className="primary" onClick={run} disabled={busy}>{busy ? 'Searching...' : set ? 'Search again' : 'Find conformers'}</button>
        </div>
      </header>
      {mini && (
        <p className="small">
          {mini.force_field} energy of the shown model: <b>{mini.before.toFixed(2)}</b> kcal/mol, after minimisation <b>{mini.after.toFixed(2)}</b> kcal/mol
          {mini.before - mini.after > 0.05 ? ` (lowered by ${(mini.before - mini.after).toFixed(2)})` : ' (already at a minimum)'}{mini.converged ? '' : '; not fully converged'}.
        </p>
      )}
      {err && <p className="error small">{err}</p>}
      {!set && !mini && !err && <p className="muted small">Embed several starting geometries, minimise each with MMFF94 and compare their energies and populations.</p>}
      {set && current && (
        <div className="bonding-split">
          <div>
            <table className="bonding-table conf-table">
              <thead>
                <tr><th>#</th><th>ΔE (kcal/mol)</th><th>Population</th><th>RMSD (Å)</th></tr>
              </thead>
              <tbody>
                {set.conformers.map((c) => (
                  <tr key={c.id} className={c.id === sel ? 'selected' : ''} onClick={() => setSel(c.id)} style={{ cursor: 'pointer' }}>
                    <td>{c.id + 1}</td>
                    <td>{c.relative.toFixed(2)}</td>
                    <td><span className="frac-bar" aria-hidden="true"><span style={{ width: `${c.population}%` }} /></span>{c.population.toFixed(1)}%</td>
                    <td>{c.rmsd.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">{set.note} Select a row to view it. RMSD is over heavy atoms against conformer 1.</p>
          </div>
          <div>
            <Structure3D mol={{ ...mol, molblock: current.molblock }} highlight={null} compact />
            <p className="small">Conformer {current.id + 1}: {current.energy.toFixed(2)} kcal/mol absolute, {current.relative.toFixed(2)} above the lowest.</p>
          </div>
        </div>
      )}
    </section>
  )
}
