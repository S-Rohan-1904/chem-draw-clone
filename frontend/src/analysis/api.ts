import { request } from '../api'
import type { AcidBase, Bonding, IsotopeLabel, IsotopeResult, SugarProjections } from './types'

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const analysisApi = {
  bonding: (smiles: string) => post<Bonding>('/api/analysis/bonding', { smiles }),
  acidBase: (smiles: string, ph: number) => post<AcidBase>('/api/analysis/acidbase', { smiles, ph }),
  sugars: (smiles: string) => post<SugarProjections>('/api/analysis/sugars', { smiles }),
  isotopes: (smiles: string, labels: IsotopeLabel[]) => post<IsotopeResult>('/api/analysis/isotopes', { smiles, labels }),
}
