export interface StereoCenter {
  atom_idx: number
  symbol: string
  label: 'R' | 'S' | 'r' | 's' | '?'
}

export interface StereoBond {
  bond_idx: number
  atoms: [number, number]
  label: 'E' | 'Z' | 'e' | 'z' | '?'
}

export interface Molecule {
  input_text: string
  source: 'iupac' | 'smiles' | 'molfile' | 'pubchem' | 'cactus'
  smiles: string
  svg: string
  molblock: string
  stereo: { centers: StereoCenter[]; double_bonds: StereoBond[]; unspecified: boolean }
  formula: string
  mw: number
  inchi: string
  inchikey: string
  cached: boolean
  warnings: string[]
  normalised_input: string
  properties: MolProperties
  groups: FunctionalGroup[]
}

export interface SavedMolecule {
  id: number
  label: string
  input_text: string
  smiles: string
  created_at: string
}

export interface AuthState {
  token: string
  username: string
}

export interface FunctionalGroup {
  name: string
  colour: string
  atoms: number[][]
}

export interface Highlight {
  atoms: number[]
  colour: string
}

export interface MolProperties {
  exact_mass: number
  logp: number
  tpsa: number
  hbd: number
  hba: number
  rotatable_bonds: number
  heavy_atoms: number
  rings: number
  aromatic_rings: number
  stereocentres: number
  charge: number
  qed: number
  lipinski_violations: number
}

export interface CheckResult {
  ok: boolean
  reason?: string
  highlight?: [number, number] | null
  warnings?: string[]
  source?: 'iupac' | 'smiles'
  lookup?: boolean
}

export interface BuildError {
  message: string
  input?: string
  highlight?: [number, number] | null
  suggestions: string[]
}

export interface PriorityRow {
  priority: number
  atom_idx: number | null
  symbol: string
  group: string
}

export interface StereoExplanation {
  kind: 'centre' | 'bond'
  label: string
  steps: string[]
  svg: string
  atom_idx?: number
  priorities?: PriorityRow[]
  has_h?: boolean
  bond_idx?: number
  atoms?: [number, number]
  ends?: { atom_idx: number; substituents: PriorityRow[] }[]
}
