import { request } from '../api'
import type { AuthState } from '../types'
import type { ConformerSet, Elemental, Minimised, SearchResult, SequenceKind, SequenceResult } from './types'

const post = <T,>(path: string, body: unknown, auth?: AuthState | null) => request<T>(path, { method: 'POST', body: JSON.stringify(body) }, auth)

export const toolsApi = {
  elemental: (smiles: string) => post<Elemental>('/api/tools/elemental', { smiles }),
  sequence: (kind: SequenceKind, sequence: string) => post<SequenceResult>('/api/tools/sequence', { kind, sequence }),
  conformers: (smiles: string, n = 8) => post<ConformerSet>('/api/tools/conformers', { smiles, n }),
  minimise: (smiles: string) => post<Minimised>('/api/tools/minimise', { smiles }),
  search: (auth: AuthState, query: string, mode: 'auto' | 'substructure' | 'similarity' = 'auto') => post<SearchResult>('/api/tools/search', { query, mode }, auth),
}
