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

export interface RecordedReaction {
  label: string
  count: number
  smiles: string
  reactants: string[]
  agents: string[]
  products: string[]
  source: 'uspto' | 'crd' | 'rhea'
  ref: string
  ref_label: string
  ref_url: string
  ec: string[]
  year: number | null
  yield: number | null
  svg: string
  atoms: number[]
}

export interface RecordedReactions {
  available: boolean
  uses: RecordedReaction[]
  makes: RecordedReaction[]
  enzyme_uses: RecordedReaction[]
  enzyme_makes: RecordedReaction[]
  stereo_ignored: boolean
  sources: { name: string; author: string; url: string; licence: string }[]
  heavy_atoms?: number
  max_atoms?: number
}

export interface LinkedCompound {
  start: number
  length: number
  name: string
  smiles?: string
}

export interface ManufactureMethod {
  text: string
  compounds: LinkedCompound[]
  reference: string
}

export interface WikipediaImage {
  file: string
  src: string
  width: number
  height: number
  after: number
  author: string
  licence: string
  page: string
}

export interface WikipediaMaking {
  available: boolean
  title: string
  section: string
  url: string
  paragraphs: { text: string; compounds: LinkedCompound[] }[]
  images: WikipediaImage[]
  stereo_ignored: boolean
  licence_url: string
}

export interface Manufacture {
  available: boolean
  methods: ManufactureMethod[]
  cid: number | null
  stereo_ignored: boolean
  url: string
  source_url: string
}

export interface Preprint {
  title: string
  authors: string
  date: string
  doi: string
  url: string
  cited_by: number | null
  snippet?: string
}

export interface ChemRxiv {
  available: boolean
  reason?: string
  query: string
  items: Preprint[]
  source: string
  match?: 'fulltext'
}

export interface JournalArticle {
  title: string
  authors: string
  journal: string
  year: number | null
  date: string
  doi: string
  pmid: string
  url: string
  cited_by: number
  type: string
}

export interface Journals {
  available: boolean
  reason?: string
  items: JournalArticle[]
  total: number
  match: 'pubchem' | 'title' | ''
  query: string
}

export interface PatentItem {
  number: string
  url: string
  year: number | null
  title: string
  date: string
  assignee: string
  reactions: { direction: 'uses' | 'makes'; label: string }[]
}

export interface Patents {
  available: boolean
  items: PatentItem[]
  cid: number | null
  pubchem_url: string
}

export interface Literature {
  chemrxiv: ChemRxiv
  journals: Journals
  patents: Patents
}

export interface ReactionClass {
  groups_lost: string[]
  groups_gained: string[]
  guess: string
}

export interface MechanismSummary {
  id: string
  name: string
  category: string
  summary: string
  steps: number
}

export interface MechanismDetail {
  id: string
  name: string
  category: string
  summary: string
  steps: { svg: string; caption: string; arrows: number; half: boolean; smiles: string }[]
}
