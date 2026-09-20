import { request } from '../api'
import type { Bonding } from './types'

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const analysisApi = {
  bonding: (smiles: string) => post<Bonding>('/api/analysis/bonding', { smiles }),
}
