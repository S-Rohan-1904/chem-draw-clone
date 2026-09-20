import { useEffect, useRef, useState } from 'react'
import * as $3Dmol from '3dmol'
import type { Highlight, Molecule } from '../types'

type Style = 'stick' | 'ballstick' | 'sphere' | 'line'

const STYLES: Record<Style, object> = {
  stick: { stick: { radius: 0.18 } },
  ballstick: { stick: { radius: 0.14 }, sphere: { scale: 0.28 } },
  sphere: { sphere: {} },
  line: { line: { linewidth: 3 } },
}

interface Props {
  mol: Molecule
  highlight: Highlight | null
}

/** 3D position of the atom with a given (RDKit) index, if loaded. */
function pos(v: $3Dmol.GLViewer, index: number): { x: number; y: number; z: number } | null {
  const a = v.selectedAtoms({ index })[0]
  return a && a.x !== undefined && a.y !== undefined && a.z !== undefined ? { x: a.x, y: a.y, z: a.z } : null
}

export function Structure3D({ mol, highlight }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const viewer = useRef<$3Dmol.GLViewer | null>(null)
  const [style, setStyle] = useState<Style>('ballstick')
  const [spin, setSpin] = useState(false)
  const [showLabels, setShowLabels] = useState(true)

  useEffect(() => {
    if (!box.current) return
    const v = $3Dmol.createViewer(box.current, { backgroundColor: 'white' })
    viewer.current = v
    const onResize = () => v.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      v.clear()
      viewer.current = null
    }
  }, [])

  // Load the model whenever the molecule changes.
  useEffect(() => {
    const v = viewer.current
    if (!v) return
    v.removeAllModels()
    v.removeAllLabels()
    v.addModel(mol.molblock, 'mol')
    v.setStyle({}, STYLES[style])
    v.zoomTo()
    v.render()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mol])

  useEffect(() => {
    const v = viewer.current
    if (!v) return
    v.setStyle({}, STYLES[style])
    if (highlight && highlight.atoms.length) {
      v.setStyle({ index: highlight.atoms }, { ...STYLES[style], sphere: { scale: 0.42, color: highlight.colour } })
    }
    v.render()
  }, [style, highlight, mol])

  useEffect(() => {
    const v = viewer.current
    if (!v) return
    v.removeAllLabels()
    if (showLabels) {
      for (const c of mol.stereo.centers) {
        const p = pos(v, c.atom_idx)
        if (!p) continue
        v.addLabel(c.label, {
          position: p,
          fontSize: 14,
          fontColor: c.label === '?' ? '#b45309' : 'white',
          backgroundColor: c.label === '?' ? '#fde68a' : '#1d4ed8',
          backgroundOpacity: 0.85,
          borderThickness: 0,
          inFront: true,
        })
      }
      for (const b of mol.stereo.double_bonds) {
        const a1 = pos(v, b.atoms[0])
        const a2 = pos(v, b.atoms[1])
        if (!a1 || !a2) continue
        v.addLabel(b.label, {
          position: { x: (a1.x + a2.x) / 2, y: (a1.y + a2.y) / 2, z: (a1.z + a2.z) / 2 },
          fontSize: 14,
          fontColor: b.label === '?' ? '#b45309' : 'white',
          backgroundColor: b.label === '?' ? '#fde68a' : '#047857',
          backgroundOpacity: 0.85,
          borderThickness: 0,
          inFront: true,
        })
      }
    }
    v.render()
  }, [showLabels, mol])

  useEffect(() => {
    viewer.current?.spin(spin ? 'y' : false)
  }, [spin])

  return (
    <section className="card">
      <header className="card-head">
        <h2>3D structure</h2>
        <div className="toolbar">
          <select value={style} onChange={(e) => setStyle(e.target.value as Style)} aria-label="Render style">
            <option value="ballstick">Ball &amp; stick</option>
            <option value="stick">Stick</option>
            <option value="sphere">Space-filling</option>
            <option value="line">Wireframe</option>
          </select>
          <label className="check">
            <input type="checkbox" checked={showLabels} onChange={(e) => setShowLabels(e.target.checked)} /> Labels
          </label>
          <button type="button" className={spin ? 'active' : ''} onClick={() => setSpin((s) => !s)}>
            {spin ? 'Stop' : 'Spin'}
          </button>
          <button type="button" onClick={() => { viewer.current?.zoomTo(); viewer.current?.render() }}>
            Reset
          </button>
        </div>
      </header>
      <div className="viewer3d" ref={box} />
    </section>
  )
}
