import { useState, type FormEvent } from 'react'
import { api, describeFailure } from '../api'
import type { AuthState } from '../types'

interface Props {
  onAuth: (a: AuthState) => void
  onClose: () => void
}

export function AuthDialog({ onAuth, onClose }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const auth = mode === 'login' ? await api.login(username, password) : await api.register(username, password)
      onAuth(auth)
    } catch (err) {
      setError(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>{mode === 'login' ? 'Log in' : 'Create account'}</h2>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required minLength={3} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
            minLength={8}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="submit" disabled={busy}>{mode === 'login' ? 'Log in' : 'Register'}</button>
          <button type="button" className="link" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
            {mode === 'login' ? 'Need an account? Register' : 'Have an account? Log in'}
          </button>
        </div>
      </form>
    </div>
  )
}
