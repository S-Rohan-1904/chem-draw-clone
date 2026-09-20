import type { AuthState, CheckResult, Molecule, SavedMolecule } from './types'

const TOKEN_KEY = 'chem.auth'

export function loadAuth(): AuthState | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY)
    return raw ? (JSON.parse(raw) as AuthState) : null
  } catch {
    return null
  }
}

export function storeAuth(auth: AuthState | null) {
  try {
    if (auth) localStorage.setItem(TOKEN_KEY, JSON.stringify(auth))
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable */
  }
}

export interface ErrorBody {
  detail?: string
  input?: string
  highlight?: [number, number] | null
  suggestions?: string[]
}

export class ApiError extends Error {
  status: number
  body: ErrorBody
  constructor(status: number, message: string, body: ErrorBody = {}) {
    super(message)
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init: RequestInit = {}, auth?: AuthState | null): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (auth) headers.Authorization = `Bearer ${auth.token}`
  const res = await fetch(path, { ...init, headers: { ...headers, ...(init.headers as Record<string, string>) } })
  if (!res.ok) {
    let detail = res.statusText
    let body: ErrorBody = {}
    try {
      body = await res.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, detail, body)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  molecule: (input: string) => request<Molecule>('/api/molecule', { method: 'POST', body: JSON.stringify({ input }) }),
  highlight: (smiles: string, atoms: number[], colour: string) =>
    request<{ svg: string }>('/api/molecule/highlight', { method: 'POST', body: JSON.stringify({ smiles, atoms, colour }) }),
  byKey: (inchikey: string) => request<Molecule>(`/api/molecule/by-key/${encodeURIComponent(inchikey)}`),
  check: (input: string) => request<CheckResult>('/api/molecule/check', { method: 'POST', body: JSON.stringify({ input }) }),
  suggest: (q: string) => request<{ names: string[] }>(`/api/molecule/suggest?q=${encodeURIComponent(q)}`),
  png: async (smiles: string, width = 1600) => {
    const res = await fetch('/api/molecule/png', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ smiles, width }),
    })
    if (!res.ok) throw new ApiError(res.status, 'PNG export failed')
    return res.blob()
  },
  register: (username: string, password: string) =>
    request<AuthState>('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username: string, password: string) =>
    request<AuthState>('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: (auth: AuthState) => request<{ id: number; username: string }>('/api/auth/me', {}, auth),
  listSaved: (auth: AuthState) => request<SavedMolecule[]>('/api/saved', {}, auth),
  save: (auth: AuthState, body: { label: string; input_text: string; smiles: string }) =>
    request<SavedMolecule>('/api/saved', { method: 'POST', body: JSON.stringify(body) }, auth),
  deleteSaved: (auth: AuthState, id: number) => request<void>(`/api/saved/${id}`, { method: 'DELETE' }, auth),
}
