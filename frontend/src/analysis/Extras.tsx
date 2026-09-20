import type { Molecule } from '../types'
import { Bonding } from './Bonding'
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
    </>
  )
}
