export interface Elemental {
  formula: string
  mw: number
  exact_mass: number
  elements: { symbol: string; count: number; atomic_weight: number; mass: number; percent: number }[]
}

export type SequenceKind = 'peptide' | 'd-peptide' | 'dna' | 'rna' | 'helm'

export interface SequenceResult {
  kind: SequenceKind
  sequence: string
  residues: number | null
  smiles: string
  formula: string
  mw: number
  heavy_atoms: number
}

export interface Conformer {
  id: number
  energy: number
  relative: number
  rmsd: number
  population: number
  molblock: string
}

export interface ConformerSet {
  force_field: string
  embedded: number
  conformers: Conformer[]
  note: string
}

export interface Minimised {
  force_field: string
  before: number
  after: number
  converged: boolean
  molblock: string
}

export interface SearchHit {
  id: number
  score: number
  atoms: number[]
}

export interface SearchResult {
  mode: 'substructure' | 'similarity'
  hits: SearchHit[]
}
