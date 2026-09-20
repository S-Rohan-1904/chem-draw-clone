import type { Molecule } from '../types'
import { AcidBase } from './AcidBase'
import { Bonding } from './Bonding'
import { Conformations } from './Conformations'
import { Isotopes } from './Isotopes'
import { SugarProjections } from './SugarProjections'
import './analysis.css'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

/** Cards from the analysis feature set, rendered under the main result. */
export function ResultExtras({ mol, onHighlight }: Props) {
  return (
    <>
      <Bonding mol={mol} onHighlight={onHighlight} />
      <SugarProjections mol={mol} onHighlight={onHighlight} />
      <Conformations mol={mol} onHighlight={onHighlight} />
      <AcidBase mol={mol} onHighlight={onHighlight} />
      <Isotopes mol={mol} onHighlight={onHighlight} />
    </>
  )
}
