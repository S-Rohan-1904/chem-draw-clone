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

export interface AcidBaseSite {
  atom_idx: number
  symbol: string
  group: string
  pka: number
  kind: 'acid' | 'base'
  in_water_range: boolean
  atoms: number[]
  fraction_ionised: number
}

export interface AcidBase {
  ph: number
  sites: AcidBaseSite[]
  net_charge: number
  species_smiles: string
  species_svg: string
  species_charge: number
  pi: number | null
  strongest_acid: string | null
  strongest_base: string | null
  note: string
}

export interface IsotopeLabel {
  atom_idx: number
  isotope: string
  count: number
}

export interface IsotopeResult {
  smiles: string
  formula: string
  exact_mass: number
  base_mass: number
  shift: number
  nominal_shift: number
  svg: string
  applied: { atom_idx: number; isotope: string; count: number; text: string }[]
  options: { atom_idx: number; symbol: string; hs: number; codes: string[] }[]
}

export interface FischerRow {
  idx: number
  kind: 'end' | 'centre' | 'mid'
  label: string
  left: { idx: number; text: string; symbol: string } | null
  right: { idx: number; text: string; symbol: string } | null
  note?: string
}

export interface Fischer {
  chain: number[]
  rows: FischerRow[]
  dl: 'D' | 'L' | null
  dl_reason: string | null
  svg: string
}

export interface Haworth {
  ring: number[]
  oxygen: number
  size: number
  kind: 'pyranose' | 'furanose'
  atoms: { num: number; label: number; idx: number; subs: { idx: number; text: string; symbol: string; up: boolean; h: boolean }[] }[]
  anomer: 'alpha' | 'beta' | null
  anomeric_up: boolean | null
  reference: { num: number; text: string; up: boolean } | null
  dl: 'D' | 'L' | null
  svg: string
  rings_available: number
}

export interface SugarProjections {
  fischer: Fischer | null
  haworth: Haworth | null
}

export interface TorsionScan {
  atoms: [number, number, number, number]
  labels: [string, string]
  start_dihedral: number
  step: number
  points: { angle: number; energy: number }[]
  barrier: number
  minima: number[]
  maxima: number[]
  unit: string
  note: string
}

export interface ChairEnergy {
  ring: number[]
  chairs: { which: 'current' | 'flipped'; energy: number; axial: { atom_idx: number; label: string }[]; equatorial: { atom_idx: number; label: string }[] }[]
  delta: number | null
  summary: string
  conformers_checked: number
  unit: string
  note: string
}

export interface PredictedReaction {
  name: string
  reagents: string
  category: string
  note: string
  products: { smiles: string[]; svgs: string[]; atoms: number[]; why: string }[]
}

export interface RetroRoute {
  name: string
  reagents: string
  target_group: string
  note: string
  precursors: { smiles: string[]; svgs: string[]; atoms: number[] }[]
}

export interface ReactionClass {
  matches: { name: string; reagents: string; category: string; explanation: string; note: string; mechanism_note: string; reactant: string; atoms: number[] }[]
  groups_lost: string[]
  groups_gained: string[]
  guess: string
}
