import { request } from '../api'
import type { AcidBase, Bonding, ChairEnergy, IsotopeLabel, IsotopeResult, SugarProjections, TorsionScan } from './types'

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const analysisApi = {
  bonding: (smiles: string) => post<Bonding>('/api/analysis/bonding', { smiles }),
  acidBase: (smiles: string, ph: number) => post<AcidBase>('/api/analysis/acidbase', { smiles, ph }),
  sugars: (smiles: string) => post<SugarProjections>('/api/analysis/sugars', { smiles }),
  scan: (smiles: string, front: number, back: number) => post<TorsionScan>('/api/analysis/scan', { smiles, front, back }),
  chairEnergy: (smiles: string, ring: number[]) => post<ChairEnergy>('/api/analysis/chair-energy', { smiles, ring }),
  isotopes: (smiles: string, labels: IsotopeLabel[]) => post<IsotopeResult>('/api/analysis/isotopes', { smiles, labels }),
}
