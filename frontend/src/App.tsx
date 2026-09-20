import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, loadAuth, storeAuth } from './api'
import { AuthDialog } from './components/AuthDialog'
import { BatchPanel } from './components/BatchPanel'
import { Compare } from './components/Compare'
import { Downloads } from './components/Downloads'
import { DrawPanel } from './components/DrawPanel'
import { ErrorPanel } from './components/ErrorPanel'
import { Gallery } from './components/Gallery'
import { Groups } from './components/Groups'
import { NameInput } from './components/NameInput'
import { Projections } from './components/Projections'
import { Properties } from './components/Properties'
import { QuizPanel } from './components/QuizPanel'
import { SavedList } from './components/SavedList'
import { ResultSkeleton } from './components/Skeleton'
import { StereoPanel } from './components/StereoPanel'
import { Structure2D } from './components/Structure2D'
import { Structure3D } from './components/Structure3D'
import { useTheme } from './theme'
import type { AuthState, BuildError, FunctionalGroup, Highlight, Molecule, SavedMolecule, StereoExplanation } from './types'

export default function App() {
  const [theme, toggleTheme] = useTheme()
  const [input, setInput] = useState('')
  const [mode, setMode] = useState<'name' | 'draw' | 'batch' | 'quiz'>('name')
  const [drawOpened, setDrawOpened] = useState(false)
  const [loadStruct, setLoadStruct] = useState<{ value: string; nonce: number } | null>(null)
  const [mol, setMol] = useState<Molecule | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<BuildError | null>(null)
  const [highlight, setHighlight] = useState<Highlight | null>(null)
  const [group, setGroup] = useState<FunctionalGroup | null>(null)
  const [groupSvg, setGroupSvg] = useState<string | null>(null)
  const [stereoSel, setStereoSel] = useState<string | null>(null)
  const [explanation, setExplanation] = useState<StereoExplanation | null>(null)
  const [compare, setCompare] = useState<{ other: Molecule; title: string } | null>(null)

  const [auth, setAuth] = useState<AuthState | null>(() => loadAuth())
  const [showAuth, setShowAuth] = useState(false)
  const [saved, setSaved] = useState<SavedMolecule[]>([])
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [saveLabel, setSaveLabel] = useState<string | null>(null) // non-null = label form open
  const [saveColl, setSaveColl] = useState('')
  const [shareMsg, setShareMsg] = useState<string | null>(null)

  const build = useCallback(async (text: string) => {
    setLoading(true)
    setError(null)
    setSaveMsg(null)
    setSaveLabel(null)
    if (window.location.pathname.startsWith('/m/')) window.history.replaceState(null, '', '/')
    setGroup(null)
    setGroupSvg(null)
    setHighlight(null)
    setStereoSel(null)
    setExplanation(null)
    setCompare(null)
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

  // Build without leaving the current tab (batch and quiz results open in place).
  const openInPlace = (name: string) => {
    setInput(name)
    void build(name)
  }

  const openDraw = () => {
    setMode('draw')
    setDrawOpened(true)
  }

  const selectGroup = (g: FunctionalGroup | null) => {
    setGroup(g)
    setStereoSel(null)
    setExplanation(null)
    if (!g || !mol) {
      setGroupSvg(null)
      setHighlight(null)
      return
    }
    const atoms = g.atoms.flat()
    setHighlight({ atoms, colour: g.colour })
    api
      .highlight(mol.smiles, atoms, g.colour)
      .then((r) => setGroupSvg(r.svg))
      .catch(() => setGroupSvg(null))
  }

  const selectStereo = (sel: { atom_idx?: number; bond_idx?: number } | null) => {
    if (!sel || !mol) {
      setStereoSel(null)
      setExplanation(null)
      if (!group) setHighlight(null)
      return
    }
    setGroup(null)
    setGroupSvg(null)
    setStereoSel(sel.atom_idx !== undefined ? `a${sel.atom_idx}` : `b${sel.bond_idx}`)
    api
      .stereo(mol.smiles, sel)
      .then((ex) => {
        setExplanation(ex)
        const atoms = ex.kind === 'centre' ? [ex.atom_idx as number] : (ex.atoms as number[])
        setHighlight({ atoms, colour: ex.kind === 'centre' ? '#2563eb' : '#047857' })
      })
      .catch(() => setExplanation(null))
  }

  const makeVariant = async (op: 'mirror' | 'invert', atomIdx?: number) => {
    if (!mol) return
    try {
      const other = await api.variant(mol.smiles, op, atomIdx)
      setCompare({ other, title: op === 'mirror' ? 'Mirror image' : 'Centre flipped' })
    } catch (e) {
      setError({ message: e instanceof ApiError ? e.message : 'Could not build the variant.', suggestions: [] })
    }
  }

  const useMolecule = (m: Molecule) => {
    setCompare(null)
    setGroup(null)
    setGroupSvg(null)
    setStereoSel(null)
    setExplanation(null)
    setHighlight(null)
    setInput(m.smiles)
    setMol(m)
  }

  const hoverAtom = (idx: number | null) => {
    if (group || stereoSel) return // a selection owns the highlight
    setHighlight(idx === null ? null : { atoms: [idx], colour: '#f59e0b' })
  }

  const share = async () => {
    if (!mol) return
    const url = `${window.location.origin}/m/${mol.inchikey}`
    window.history.replaceState(null, '', `/m/${mol.inchikey}`)
    try {
      await navigator.clipboard.writeText(url)
      setShareMsg('Link copied')
    } catch {
      setShareMsg(url)
    }
    window.setTimeout(() => setShareMsg(null), 2500)
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

  // Shared link: /m/<inchikey>
  useEffect(() => {
    const m = window.location.pathname.match(/^\/m\/([A-Z]{14}-[A-Z]{10}-[A-Z])$/i)
    if (!m) return
    setLoading(true)
    api
      .byKey(m[1])
      .then((res) => {
        setMol(res)
        setInput(res.source === 'molfile' ? res.smiles : res.input_text)
      })
      .catch((e) => setError({ message: e instanceof ApiError ? e.message : 'Could not load the shared molecule.', suggestions: [] }))
      .finally(() => setLoading(false))
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
      const row = await api.save(auth, {
        label: saveLabel.trim() || mol.input_text,
        input_text: mol.source === 'molfile' ? mol.smiles : mol.input_text,
        smiles: mol.smiles,
        collection: saveColl.trim(),
      })
      setSaved((s) => [row, ...s])
      setSaveMsg('Saved.')
      setSaveLabel(null)
    } catch (e) {
      setSaveMsg(e instanceof ApiError ? e.message : 'Save failed')
    }
  }

  const updateSaved = async (id: number, patch: { notes?: string; collection?: string; label?: string }) => {
    if (!auth) return
    const row = await api.updateSaved(auth, id, patch)
    setSaved((s) => s.map((x) => (x.id === id ? row : x)))
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
          <button type="button" className="theme-toggle" onClick={toggleTheme} title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'} aria-label="Toggle dark mode">
            {theme === 'dark' ? '☀' : '☾'}
          </button>
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
        <button type="button" role="tab" aria-selected={mode === 'batch'} className={mode === 'batch' ? 'active' : ''} onClick={() => setMode('batch')}>Batch</button>
        <button type="button" role="tab" aria-selected={mode === 'quiz'} className={mode === 'quiz' ? 'active' : ''} onClick={() => setMode('quiz')}>Quiz</button>
      </div>
      <div hidden={mode !== 'name'}>
        <NameInput value={input} onChange={setInput} onSubmit={build} loading={loading} showHint={!error} />
      </div>
      {drawOpened && (
        <div hidden={mode !== 'draw'}>
          <DrawPanel onBuild={build} loading={loading} loadStruct={loadStruct} />
        </div>
      )}
      <div hidden={mode !== 'batch'}>
        <BatchPanel onOpen={openInPlace} />
      </div>
      {mode === 'quiz' && <QuizPanel auth={auth} onOpen={pick} />}
      {error && <ErrorPanel error={error} onPick={pick} />}

      <div className="layout" hidden={mode === 'quiz'}>
        <aside className="side">
          <Gallery onPick={pick} />
          {auth && <SavedList items={saved} onPick={(it) => pick(it.input_text)} onDelete={remove} onUpdate={updateSaved} />}
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
                  {(mol.source === 'pubchem' || mol.source === 'cactus') && <span className="tag">looked up</span>}
                  {mol.cached && <span className="tag">cached</span>}
                </div>
                <div className="result-actions">
                  <button type="button" onClick={editStructure}>Copy to editor</button>
                  <button type="button" onClick={() => void share()}>Share</button>
                  {shareMsg && <span className="muted small">{shareMsg}</span>}
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
                      <input list="collections" value={saveColl} onChange={(e) => setSaveColl(e.target.value)} aria-label="Collection" placeholder="Collection (optional)" />
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
                <Structure2D
                  mol={mol}
                  svg={explanation ? explanation.svg : groupSvg}
                  caption={explanation ? `CIP priorities for ${explanation.label}` : group ? group.name : null}
                />
                <Structure3D mol={mol} highlight={highlight} />
              </div>
              <div className="grid2">
                <StereoPanel
                  mol={mol}
                  onHover={hoverAtom}
                  onSelect={selectStereo}
                  selected={stereoSel}
                  explanation={explanation}
                  onVariant={(op, idx) => void makeVariant(op, idx)}
                />
                <Properties mol={mol} />
              </div>
              {compare && <Compare base={mol} other={compare.other} title={compare.title} onClose={() => setCompare(null)} onUse={useMolecule} />}
              <Projections mol={mol} onHighlight={(atoms) => { if (!group && !stereoSel) setHighlight(atoms ? { atoms, colour: '#f59e0b' } : null) }} />
              <div className="grid2">
                <Groups mol={mol} active={group?.name ?? null} onSelect={selectGroup} />
              </div>
              <Downloads mol={mol} />
            </>
          )}
        </main>
      </div>

      {showAuth && <AuthDialog onAuth={onAuth} onClose={() => setShowAuth(false)} />}
    </div>
  )
}
