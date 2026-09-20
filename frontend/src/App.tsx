import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, loadAuth, storeAuth } from './api'
import { AuthDialog } from './components/AuthDialog'
import { Downloads } from './components/Downloads'
import { DrawPanel } from './components/DrawPanel'
import { ErrorPanel } from './components/ErrorPanel'
import { Gallery } from './components/Gallery'
import { NameInput } from './components/NameInput'
import { SavedList } from './components/SavedList'
import { ResultSkeleton } from './components/Skeleton'
import { StereoPanel } from './components/StereoPanel'
import { Structure2D } from './components/Structure2D'
import { Structure3D } from './components/Structure3D'
import type { AuthState, BuildError, Molecule, SavedMolecule } from './types'

export default function App() {
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<'name' | 'draw'>('name')
  const [drawOpened, setDrawOpened] = useState(false)
  const [loadStruct, setLoadStruct] = useState<{ value: string; nonce: number } | null>(null)
  const [mol, setMol] = useState<Molecule | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<BuildError | null>(null)
  const [highlight, setHighlight] = useState<number | null>(null)

  const [auth, setAuth] = useState<AuthState | null>(() => loadAuth())
  const [showAuth, setShowAuth] = useState(false)
  const [saved, setSaved] = useState<SavedMolecule[]>([])
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [saveLabel, setSaveLabel] = useState<string | null>(null) // non-null = label form open

  const build = useCallback(async (text: string) => {
    setLoading(true)
    setError(null)
    setSaveMsg(null)
    setSaveLabel(null)
    try {
      setMol(await api.molecule(text))
    } catch (e) {
      setMol(null)
      if (e instanceof ApiError) {
        setError({ message: e.message, input: e.body.input, highlight: e.body.highlight ?? null, suggestions: e.body.suggestions ?? [] })
      } else {
        setError({ message: 'Could not reach the server.', suggestions: [] })
      }
    } finally {
      setLoading(false)
    }
  }, [])

  const pick = (name: string) => {
    setInput(name)
    setMode('name')
    void build(name)
  }

  const openDraw = () => {
    setMode('draw')
    setDrawOpened(true)
  }

  const editStructure = () => {
    if (!mol) return
    openDraw()
    setLoadStruct({ value: mol.smiles, nonce: Date.now() })
  }

  const logout = useCallback(() => {
    setAuth(null)
    storeAuth(null)
    setSaved([])
  }, [])

  // Validate stored token and load saved list.
  useEffect(() => {
    if (!auth) return
    api
      .me(auth)
      .then(() => api.listSaved(auth))
      .then(setSaved)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) logout()
      })
  }, [auth, logout])

  const onAuth = (a: AuthState) => {
    setAuth(a)
    storeAuth(a)
    setShowAuth(false)
  }

  const openSave = () => {
    if (!mol) return
    if (!auth) {
      setShowAuth(true)
      return
    }
    setSaveLabel(mol.input_text)
  }

  const save = async () => {
    if (!mol || !auth || saveLabel === null) return
    try {
      const row = await api.save(auth, { label: saveLabel.trim() || mol.input_text, input_text: mol.input_text, smiles: mol.smiles })
      setSaved((s) => [row, ...s])
      setSaveMsg('Saved.')
      setSaveLabel(null)
    } catch (e) {
      setSaveMsg(e instanceof ApiError ? e.message : 'Save failed')
    }
  }

  const remove = async (id: number) => {
    if (!auth) return
    await api.deleteSaved(auth, id)
    setSaved((s) => s.filter((x) => x.id !== id))
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>IUPAC Structure Viewer</h1>
          <p className="muted">2D and 3D structures from IUPAC names</p>
        </div>
        <div className="auth">
          {auth ? (
            <>
              <span>Signed in as <b>{auth.username}</b></span>
              <button type="button" onClick={logout}>Log out</button>
            </>
          ) : (
            <button type="button" onClick={() => setShowAuth(true)}>Log in / Register</button>
          )}
        </div>
      </header>

      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === 'name'} className={mode === 'name' ? 'active' : ''} onClick={() => setMode('name')}>Name</button>
        <button type="button" role="tab" aria-selected={mode === 'draw'} className={mode === 'draw' ? 'active' : ''} onClick={openDraw}>Draw</button>
      </div>
      <div hidden={mode !== 'name'}>
        <NameInput value={input} onChange={setInput} onSubmit={build} loading={loading} showHint={!error} />
      </div>
      {drawOpened && (
        <div hidden={mode !== 'draw'}>
          <DrawPanel onBuild={build} loading={loading} loadStruct={loadStruct} />
        </div>
      )}
      {error && <ErrorPanel error={error} onPick={pick} />}

      <div className="layout">
        <aside className="side">
          <Gallery onPick={pick} />
          {auth && <SavedList items={saved} onPick={(it) => pick(it.input_text)} onDelete={remove} />}
        </aside>

        <main className="main">
          {!mol && !loading && (
            <section className="card empty">
              <p>Enter a name or pick an example.</p>
            </section>
          )}
          {loading && <ResultSkeleton />}
          {mol && !loading && (
            <>
              <div className="result-bar">
                <div>
                  <b>{mol.source === 'molfile' ? mol.smiles : mol.input_text}</b>
                  {mol.source === 'molfile' && <span className="tag">drawn</span>}
                  {mol.cached && <span className="tag">cached</span>}
                </div>
                <div className="result-actions">
                  <button type="button" onClick={editStructure}>Edit structure</button>
                  {saveLabel === null ? (
                    <button type="button" className="primary" onClick={openSave}>Save</button>
                  ) : (
                    <form
                      className="save-form"
                      onSubmit={(e) => {
                        e.preventDefault()
                        void save()
                      }}
                    >
                      <input value={saveLabel} onChange={(e) => setSaveLabel(e.target.value)} aria-label="Label" placeholder="Label" autoFocus />
                      <button type="submit" className="primary">Save</button>
                      <button type="button" onClick={() => setSaveLabel(null)}>Cancel</button>
                    </form>
                  )}
                  {saveMsg && <span className="muted small">{saveMsg}</span>}
                </div>
              </div>
              {mol.warnings.length > 0 && (
                <div className="warn-banner">
                  {mol.warnings.map((w) => <p key={w}>{w}</p>)}
                </div>
              )}
              {mol.normalised_input && mol.normalised_input !== mol.input_text && (
                <p className="muted small">Interpreted as <code>{mol.normalised_input}</code></p>
              )}
              <div className="grid2">
                <Structure2D mol={mol} />
                <Structure3D mol={mol} highlight={highlight} />
              </div>
              <StereoPanel mol={mol} onHover={setHighlight} />
              <Downloads mol={mol} />
            </>
          )}
        </main>
      </div>

      {showAuth && <AuthDialog onAuth={onAuth} onClose={() => setShowAuth(false)} />}
    </div>
  )
}
