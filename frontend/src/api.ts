import type { AdminStats, AlignResult, Assignment, AssignmentAnswer, AssignmentProgress, AuthState, BatchRow, IsomerResult, NameBreakdown, QuizStats, ReactionResult, NameLookup, ChairOut, CheckResult, Molecule, NewmanOut, ProjectionInfo, QuizAnswer, QuizQuestion, SavedMolecule, StereoExplanation } from './types'

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

const TIMEOUT_MS = 90_000

/** Plain-language message for failures that are not the user's fault. */
export function describeFailure(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return e.message
    if (e.status === 429) return 'Too many requests in a short time. Wait a few seconds and try again.'
    if (e.status === 502 || e.status === 503 || e.status === 504) return 'The server is starting up (this takes about a minute after it has been idle). Try again shortly.'
    if (e.status >= 500) return 'The server hit an error building this molecule. Try a smaller or simpler input.'
    return e.message
  }
  return 'Could not reach the server. Check your connection; if the site was idle it may take a minute to wake up.'
}

async function request<T>(path: string, init: RequestInit = {}, auth?: AuthState | null): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (auth) headers.Authorization = `Bearer ${auth.token}`
  const ctrl = new AbortController()
  const timer = window.setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(path, { ...init, headers: { ...headers, ...(init.headers as Record<string, string>) }, signal: ctrl.signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw new ApiError(0, 'This took too long. The free server is slow for large molecules; try a smaller input or wait and retry.')
    throw new ApiError(0, 'Could not reach the server. Check your connection; if the site was idle it may take a minute to wake up.')
  } finally {
    window.clearTimeout(timer)
  }
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
  stereo: (smiles: string, sel: { atom_idx?: number; bond_idx?: number }) =>
    request<StereoExplanation>('/api/molecule/stereo', { method: 'POST', body: JSON.stringify({ smiles, ...sel }) }),
  variant: (smiles: string, op: 'mirror' | 'invert', atom_idx?: number) =>
    request<Molecule>('/api/molecule/variant', { method: 'POST', body: JSON.stringify({ smiles, op, atom_idx }) }),
  batch: (inputs: string[]) => request<{ rows: BatchRow[] }>('/api/molecule/batch', { method: 'POST', body: JSON.stringify({ inputs }) }),
  quizQuestion: (level: number, exclude: string[]) =>
    request<QuizQuestion>(`/api/quiz/question?level=${level}&exclude=${encodeURIComponent(exclude.join(','))}`),
  quizAnswer: (auth: AuthState | null, body: { id: string; answer: string; attempt: number; reveal?: boolean }) =>
    request<QuizAnswer>('/api/quiz/answer', { method: 'POST', body: JSON.stringify(body) }, auth),
  projections: (smiles: string) => request<ProjectionInfo>('/api/molecule/projections', { method: 'POST', body: JSON.stringify({ smiles }) }),
  newman: (smiles: string, front: number, back: number, rotate: number) =>
    request<NewmanOut>('/api/molecule/newman', { method: 'POST', body: JSON.stringify({ smiles, front, back, rotate }) }),
  chair: (smiles: string, ring: number[]) => request<ChairOut>('/api/molecule/chair', { method: 'POST', body: JSON.stringify({ smiles, ring }) }),
  lookupName: (inchikey: string) => request<NameLookup>(`/api/molecule/name/${encodeURIComponent(inchikey)}`),
  resonance: (smiles: string) => request<{ forms: { svg: string; smiles: string }[] }>('/api/molecule/resonance', { method: 'POST', body: JSON.stringify({ smiles }) }),
  charges: (smiles: string) => request<{ charges: number[]; min: number; max: number }>('/api/molecule/charges', { method: 'POST', body: JSON.stringify({ smiles }) }),
  isomers: (formula: string) => request<IsomerResult>(`/api/isomers?formula=${encodeURIComponent(formula)}`),
  breakdown: (name: string, smiles: string) => request<NameBreakdown>('/api/molecule/breakdown', { method: 'POST', body: JSON.stringify({ name, smiles }) }),
  reaction: (text: string) => request<ReactionResult>('/api/molecule/reaction', { method: 'POST', body: JSON.stringify({ text }) }),
  quizStats: (auth: AuthState) => request<QuizStats>('/api/quiz/stats', {}, auth),
  createAssignment: (auth: AuthState, title: string, names: string[]) =>
    request<{ assignment: Assignment; rejected: { name: string; reason: string }[] }>('/api/assignments', { method: 'POST', body: JSON.stringify({ title, names }) }, auth),
  myAssignments: (auth: AuthState) => request<Assignment[]>('/api/assignments/mine', {}, auth),
  joinedAssignments: (auth: AuthState) => request<Assignment[]>('/api/assignments/joined', {}, auth),
  getAssignment: (code: string, auth: AuthState | null) => request<Assignment>(`/api/assignments/${encodeURIComponent(code)}${auth ? '/me' : ''}`, {}, auth),
  answerAssignment: (auth: AuthState, code: string, itemId: number, answer: string, attempt: number) =>
    request<AssignmentAnswer>(`/api/assignments/${encodeURIComponent(code)}/answer/${itemId}`, { method: 'POST', body: JSON.stringify({ answer, attempt }) }, auth),
  assignmentProgress: (auth: AuthState, code: string) => request<AssignmentProgress>(`/api/assignments/${encodeURIComponent(code)}/progress`, {}, auth),
  deleteAssignment: (auth: AuthState, code: string) => request<void>(`/api/assignments/${encodeURIComponent(code)}`, { method: 'DELETE' }, auth),
  worksheet: async (title: string, items: { name: string; smiles: string }[], showNames: boolean) => {
    const res = await fetch('/api/worksheet', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title, items, show_names: showNames, answer_key: true }) })
    if (!res.ok) throw new ApiError(res.status, 'Worksheet failed')
    return res.blob()
  },
  align: (a: string, b: string) => request<AlignResult>('/api/molecule/align', { method: 'POST', body: JSON.stringify({ smiles_a: a, smiles_b: b }) }),
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
  me: (auth: AuthState) => request<{ id: number; username: string; is_admin: boolean }>('/api/auth/me', {}, auth),
  adminStats: (auth: AuthState, days = 14) => request<AdminStats>(`/api/admin/stats?days=${days}`, {}, auth),
  listSaved: (auth: AuthState) => request<SavedMolecule[]>('/api/saved', {}, auth),
  save: (auth: AuthState, body: { label: string; input_text: string; smiles: string; collection?: string; notes?: string }) =>
    request<SavedMolecule>('/api/saved', { method: 'POST', body: JSON.stringify(body) }, auth),
  updateSaved: (auth: AuthState, id: number, body: { label?: string; collection?: string; notes?: string }) =>
    request<SavedMolecule>(`/api/saved/${id}`, { method: 'PATCH', body: JSON.stringify(body) }, auth),
  deleteSaved: (auth: AuthState, id: number) => request<void>(`/api/saved/${id}`, { method: 'DELETE' }, auth),
}
