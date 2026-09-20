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
  compact?: boolean
}

type Vec = { x: number; y: number; z: number }
const sub = (a: Vec, b: Vec): Vec => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z })
const dot = (a: Vec, b: Vec) => a.x * b.x + a.y * b.y + a.z * b.z
const cross = (a: Vec, b: Vec): Vec => ({ x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x })
const norm = (a: Vec) => Math.sqrt(dot(a, a))
const mid = (ps: Vec[]): Vec => ({ x: ps.reduce((s, p) => s + p.x, 0) / ps.length, y: ps.reduce((s, p) => s + p.y, 0) / ps.length, z: ps.reduce((s, p) => s + p.z, 0) / ps.length })

/** Distance (2 points), angle (3) or dihedral (4). */
function measure(ps: Vec[]): string {
  if (ps.length === 2) return `${norm(sub(ps[0], ps[1])).toFixed(2)} \u00c5`
  if (ps.length === 3) {
    const a = sub(ps[0], ps[1]), b = sub(ps[2], ps[1])
    return `${((Math.acos(dot(a, b) / (norm(a) * norm(b))) * 180) / Math.PI).toFixed(1)}\u00b0`
  }
  if (ps.length === 4) {
    const b1 = sub(ps[1], ps[0]), b2 = sub(ps[2], ps[1]), b3 = sub(ps[3], ps[2])
    const n1 = cross(b1, b2), n2 = cross(b2, b3)
    const m1 = cross(n1, { x: b2.x / norm(b2), y: b2.y / norm(b2), z: b2.z / norm(b2) })
    const x = dot(n1, n2), y = dot(m1, n2)
    return `${((Math.atan2(y, x) * 180) / Math.PI).toFixed(1)}\u00b0`
  }
  return ''
}

/** 3D position of the atom with a given (RDKit) index, if loaded. */
function pos(v: $3Dmol.GLViewer, index: number): { x: number; y: number; z: number } | null {
  const a = v.selectedAtoms({ index })[0]
  return a && a.x !== undefined && a.y !== undefined && a.z !== undefined ? { x: a.x, y: a.y, z: a.z } : null
}

export function Structure3D({ mol, highlight, compact = false }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const viewer = useRef<$3Dmol.GLViewer | null>(null)
  const [style, setStyle] = useState<Style>('ballstick')
  const [spin, setSpin] = useState(false)
  const [showLabels, setShowLabels] = useState(true)
  const [measuring, setMeasuring] = useState(false)
  const [showHyb, setShowHyb] = useState(false)
  const hybLabels = useRef<unknown[]>([])
  const [picked, setPicked] = useState<number[]>([])
  const [reading, setReading] = useState<string | null>(null)
  const pickedRef = useRef<number[]>([])
  const measureLabel = useRef<unknown>(null)

  useEffect(() => {
    if (!box.current) return
    const v = $3Dmol.createViewer(box.current, { backgroundColor: 'white' })
    viewer.current = v
    if (!compact) (window as unknown as { viewer3d?: $3Dmol.GLViewer }).viewer3d = v
    const onResize = () => v.resize()
    window.addEventListener('resize', onResize)
    const el = box.current
    return () => {
      window.removeEventListener('resize', onResize)
      v.clear()
      viewer.current = null
      el.replaceChildren() // drop the canvases so a remount does not stack a stale one underneath
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
    measureLabel.current = null
    if (pickedRef.current.length >= 2) drawMeasure(v, pickedRef.current)
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

  // Draw the current measurement: picked atoms, connecting lines, value label.
  const drawMeasure = (v: $3Dmol.GLViewer, atoms: number[]) => {
    v.removeAllShapes()
    if (measureLabel.current) {
      v.removeLabel(measureLabel.current as Parameters<$3Dmol.GLViewer['removeLabel']>[0])
      measureLabel.current = null
    }
    const ps = atoms.map((i) => pos(v, i)).filter((p): p is Vec => p !== null)
    for (let i = 0; i + 1 < ps.length; i++) {
      v.addCylinder({ start: ps[i], end: ps[i + 1], radius: 0.06, color: '#f59e0b', dashed: true })
    }
    ps.forEach((p) => v.addSphere({ center: p, radius: 0.32, color: '#f59e0b', alpha: 0.6 }))
    const value = measure(ps)
    if (value) {
      measureLabel.current = v.addLabel(value, { position: mid(ps), fontSize: 15, fontColor: 'black', backgroundColor: '#fde68a', backgroundOpacity: 0.95, borderThickness: 0, inFront: true })
    }
    setReading(value || null)
  }

  useEffect(() => {
    const v = viewer.current
    if (!v) return
    v.setClickable({}, measuring, (atom: { index?: number }) => {
      if (atom.index === undefined) return
      let next = [...pickedRef.current]
      if (next.length >= 4 || next[next.length - 1] === atom.index) next = []
      next.push(atom.index)
      pickedRef.current = next
      setPicked(next)
      drawMeasure(v, next)
      v.render()
    })
    v.render() // clickables are only rebuilt on render
    if (!measuring) {
      pickedRef.current = []
      setPicked([])
      setReading(null)
      v.removeAllShapes()
      v.render()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measuring, mol])

  const clearMeasure = () => {
    const v = viewer.current
    pickedRef.current = []
    setPicked([])
    setReading(null)
    if (v) {
      v.removeAllShapes()
      if (measureLabel.current) {
        v.removeLabel(measureLabel.current as Parameters<$3Dmol.GLViewer['removeLabel']>[0])
        measureLabel.current = null
      }
      v.render()
    }
  }

  // Hover tooltip with hybridisation and lone pairs; optional labels on heavy atoms.
  useEffect(() => {
    const v = viewer.current
    if (!v) return
    const info = new Map((mol.atoms ?? []).map((a) => [a.idx, a]))
    const describe = (a: { index?: number; elem?: string }) => {
      const row = a.index !== undefined ? info.get(a.index) : undefined
      if (!row) return a.elem === 'H' ? 'H' : a.elem ?? ''
      const bits = [`${row.symbol}${row.idx + 1}`, row.hybridization]
      if (row.lone_pairs) bits.push(`${row.lone_pairs} lone pair${row.lone_pairs > 1 ? 's' : ''}`)
      if (row.charge) bits.push(`charge ${row.charge > 0 ? '+' : ''}${row.charge}`)
      return bits.join(' · ')
    }
    let hoverLabel: unknown = null
    v.setHoverable(
      {},
      true,
      (atom: { index?: number; elem?: string; x: number; y: number; z: number }) => {
        if (hoverLabel) v.removeLabel(hoverLabel as Parameters<$3Dmol.GLViewer['removeLabel']>[0])
        hoverLabel = v.addLabel(describe(atom), {
          position: { x: atom.x, y: atom.y, z: atom.z },
          fontSize: 12,
          backgroundColor: '#1a1d29',
          backgroundOpacity: 0.85,
          fontColor: 'white',
          borderThickness: 0,
          inFront: true,
        })
        v.render()
      },
      () => {
        if (hoverLabel) {
          v.removeLabel(hoverLabel as Parameters<$3Dmol.GLViewer['removeLabel']>[0])
          hoverLabel = null
          v.render()
        }
      },
    )
    v.render()
    return () => {
      if (hoverLabel) v.removeLabel(hoverLabel as Parameters<$3Dmol.GLViewer['removeLabel']>[0])
    }
  }, [mol])

  useEffect(() => {
    const v = viewer.current
    if (!v) return
    for (const l of hybLabels.current) v.removeLabel(l as Parameters<$3Dmol.GLViewer['removeLabel']>[0])
    hybLabels.current = []
    if (showHyb) {
      for (const a of mol.atoms ?? []) {
        if (a.symbol === 'H') continue
        const p = pos(v, a.idx)
        if (!p) continue
        const text = a.lone_pairs ? `${a.hybridization} · ${a.lone_pairs}lp` : a.hybridization
        hybLabels.current.push(
          v.addLabel(text, { position: p, fontSize: 11, fontColor: '#1a1d29', backgroundColor: '#e2e8f0', backgroundOpacity: 0.9, borderThickness: 0, inFront: true }),
        )
      }
    }
    v.render()
  }, [showHyb, mol, showLabels])

  useEffect(() => {
    viewer.current?.spin(spin ? 'y' : false)
  }, [spin])

  if (compact) {
    return <div className="viewer3d viewer3d-compact" ref={box} />
  }

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
          <label className="check" title="Show hybridisation and lone pairs on each heavy atom">
            <input type="checkbox" checked={showHyb} onChange={(e) => setShowHyb(e.target.checked)} /> Orbitals
          </label>
          <button type="button" className={spin ? 'active' : ''} onClick={() => setSpin((s) => !s)}>
            {spin ? 'Stop' : 'Spin'}
          </button>
          <button type="button" onClick={() => { viewer.current?.zoomTo(); viewer.current?.render() }}>
            Reset
          </button>
          <button type="button" className={measuring ? 'active' : ''} onClick={() => setMeasuring((m) => !m)} title="Click 2 atoms for a distance, 3 for an angle, 4 for a dihedral">
            Measure
          </button>
        </div>
      </header>
      <div className={`viewer3d ${measuring ? 'measuring' : ''}`} ref={box} />
      {measuring && (
        <p className="measure-bar">
          {picked.length === 0 && 'Click atoms: 2 for distance, 3 for angle, 4 for dihedral.'}
          {picked.length === 1 && 'Pick another atom.'}
          {reading && <b>{picked.length === 2 ? 'Distance' : picked.length === 3 ? 'Angle' : 'Dihedral'}: {reading}</b>}
          {picked.length > 0 && <button type="button" className="link" onClick={clearMeasure}>Clear</button>}
        </p>
      )}
    </section>
  )
}
