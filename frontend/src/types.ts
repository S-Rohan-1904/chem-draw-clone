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
  source: 'iupac' | 'smiles' | 'molfile'
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

export interface CheckResult {
  ok: boolean
  reason?: string
  highlight?: [number, number] | null
  warnings?: string[]
  source?: 'iupac' | 'smiles'
}

export interface BuildError {
  message: string
  input?: string
  highlight?: [number, number] | null
  suggestions: string[]
}
