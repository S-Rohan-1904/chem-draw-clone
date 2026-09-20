import { useEffect, useRef, useState, type FormEvent } from 'react'
import * as $3Dmol from '3dmol'
import { api, describeFailure } from '../api'
import type { AlignResult, Molecule } from '../types'

interface Props {
  mol: Molecule
  onClose: () => void
}

export function Overlay({ mol, onClose }: Props) {
  const [other, setOther] = useState('')
  const [otherMol, setOtherMol] = useState<Molecule | null>(null)
  const [res, setRes] = useState<AlignResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const viewer = useRef<$3Dmol.GLViewer | null>(null)

  useEffect(() => {
    if (!box.current) return
    const v = $3Dmol.createViewer(box.current, { backgroundColor: 'white' })
    viewer.current = v
    const el = box.current
    return () => {
      v.clear()
      viewer.current = null
      el.replaceChildren()
    }
  }, [])

  useEffect(() => {
    const v = viewer.current
    if (!v || !res) return
    v.removeAllModels()
    v.removeAllLabels()
    v.addModel(res.molblock_a, 'mol')
    v.addModel(res.molblock_b, 'mol')
    v.setStyle({ model: 0 }, { stick: { radius: 0.16, color: '#2563eb' } })
    v.setStyle({ model: 1 }, { stick: { radius: 0.16, color: '#f59e0b' } })
    v.setStyle({ model: 0, elem: 'O' }, { stick: { radius: 0.16, color: '#1d4ed8' } })
    v.zoomTo()
    v.render()
  }, [res])

  const run = async (e: FormEvent) => {
    e.preventDefault()
    if (!other.trim()) return
    setBusy(true)
    setError(null)
    try {
      const b = await api.molecule(other.trim())
      setOtherMol(b)
      setRes(await api.align(mol.smiles, b.smiles))
    } catch (err) {
      setRes(null)
      setError(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <header className="card-head">
        <h2>Overlay with another molecule</h2>
        <button type="button" onClick={onClose}>Close</button>
      </header>
      <form className="draw-actions" onSubmit={run}>
        <input value={other} onChange={(e) => setOther(e.target.value)} placeholder="Second molecule: name or SMILES" aria-label="Second molecule" style={{ flex: '1 1 260px' }} autoFocus />
        <button type="submit" className="primary" disabled={busy || !other.trim()}>{busy ? 'Aligning...' : 'Overlay'}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {res && otherMol && (
        <>
          <p className="overlay-legend">
            <span className="swatch" style={{ background: '#2563eb' }} /> {mol.source === 'molfile' ? mol.smiles : mol.input_text}
            <span className="swatch" style={{ background: '#f59e0b', marginLeft: '1rem' }} /> {otherMol.source === 'molfile' ? otherMol.smiles : otherMol.input_text}
          </p>
          <p className="muted small">
            RMSD {res.rmsd} Å over {res.common_atoms} common heavy atoms ({res.heavy_a} and {res.heavy_b} in total).
            {res.identical_connectivity ? ' Same connectivity: the difference is stereochemistry or conformation.' : ''}
            {res.rmsd < 0.3 ? ' Superimposable.' : res.identical_connectivity && res.rmsd > 0.5 ? ' Not superimposable: these are stereoisomers or different conformers.' : ''}
          </p>
        </>
      )}
      <div className={`viewer3d ${res ? '' : 'hidden-viewer'}`} ref={box} />
    </section>
  )
}
