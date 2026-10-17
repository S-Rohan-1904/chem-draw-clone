import { useEffect, useRef } from 'react'
import * as $3Dmol from '3dmol'
import type { IrCalculated } from '../types'

/** One normal mode animated: the molecule from GFN2-xTB with each atom swinging along its displacement. */
export function ModeViewer({ calc, mode }: { calc: IrCalculated; mode: number }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!box.current) return
    const m = calc.modes[mode]
    // XYZ with three extra columns per atom: 3Dmol reads them as the vibration's displacement vector.
    const xyz = `${calc.atoms.length}\n${m.freq} cm-1\n` + calc.atoms
      .map((a, i) => `${a.el} ${a.x} ${a.y} ${a.z} ${m.disp[i][0]} ${m.disp[i][1]} ${m.disp[i][2]}`).join('\n')
    const v = $3Dmol.createViewer(box.current, { backgroundColor: 'white' })
    const model = v.addModel(xyz, 'xyz')
    model.setStyle({}, { stick: { radius: 0.14 }, sphere: { scale: 0.22 } })
    model.vibrate(16, 0.7, true)
    v.zoomTo()
    v.animate({ loop: 'backAndForth', reps: 0, interval: 40 })
    v.render()
    return () => {
      v.stopAnimate()
      v.clear()
    }
  }, [calc, mode])
  return <div ref={box} className="mode-viewer" />
}
