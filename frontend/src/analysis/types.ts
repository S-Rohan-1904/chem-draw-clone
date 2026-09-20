export interface OxidationAtom {
  idx: number
  symbol: string
  oxidation_state: number
  formal_charge: number
  terms: string[]
}

export interface PolarBond {
  bond_idx: number
  atoms: [number, number]
  label: string
  delta_en: number
  class: 'nonpolar' | 'polar' | 'ionic'
  negative_end: number | null
}

export interface Dipole {
  debye: number
  vector: [number, number, number]
  centre: [number, number, number]
  net_charge: number
}

export interface VseprAtom {
  idx: number
  symbol: string
  domains: number
  bonded: number
  lone_pairs: number
  shape: string
  ideal_angle: number | null
  model_angle: number | null
  note: string
}

export interface RingInfo {
  atoms: number[]
  size: number
  pi_electrons: number
  aromatic: boolean
  conjugated: boolean
  verdict: string
  details: string[]
}

export interface Unsaturation {
  dbe: number
  from_formula: string
  formula_terms: string
  rings: number
  double_bonds: number
  triple_bonds: number
  structural: number
  breakdown: string
  consistent: boolean
  note: string
}

export interface ChiralityClass {
  kind: 'chiral' | 'achiral' | 'meso' | 'unknown'
  title: string
  reason: string
  centres: number[]
  unspecified: number[]
  pairs: [number, number][]
}

export interface Solubility {
  logs: number
  mol_per_l: number
  g_per_l: number
  class: string
  text: string
  reasons: string[]
  logp: number
  method: string
}

export interface Bonding {
  oxidation: { atoms: OxidationAtom[]; svg: string }
  polarity: { bonds: PolarBond[]; ch: { label: string; delta_en: number; class: string } | null; svg: string; dipole: Dipole | null }
  vsepr: VseprAtom[]
  rings: RingInfo[]
  unsaturation: Unsaturation
  chirality: ChiralityClass
  hbond: { donors: number[]; acceptors: number[]; both: number[]; svg: string }
  solubility: Solubility
}
