import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import type { EditorHandle } from './KetcherEditor'

const KetcherEditor = lazy(() => import('./KetcherEditor'))

interface Props {
  onBuild: (molfile: string) => void
  loading: boolean
  /** SMILES to load into the editor; changes trigger a load. */
  loadStruct: { value: string; nonce: number } | null
}

export function DrawPanel({ onBuild, loading, loadStruct }: Props) {
  const handle = useRef<EditorHandle | null>(null)
  const [ready, setReady] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const pending = useRef<string | null>(null)

  // Keep the structure pending until an editor instance actually takes it.
  const load = useCallback(async (h: EditorHandle, value: string) => {
    pending.current = null
    try {
      await h.setMolecule(value)
    } catch {
      pending.current ??= value
    }
  }, [])

  const onReady = useCallback((h: EditorHandle) => {
    handle.current = h
    setReady(true)
    if (pending.current) void load(h, pending.current)
  }, [load])

  useEffect(() => {
    if (!loadStruct) return
    if (handle.current) void load(handle.current, loadStruct.value)
    else pending.current = loadStruct.value
  }, [loadStruct, load])

  const build = async () => {
    if (!handle.current) return
    setMsg(null)
    const mol = await handle.current.getMolfile()
    if (!/^\s*\S/m.test(mol) || !mol.includes('M  END')) {
      setMsg('Nothing drawn yet.')
      return
    }
    onBuild(mol)
  }

  return (
    <div className="draw-panel">
      <div className="editor-wrap">
        <Suspense fallback={<div className="editor-loading">Loading editor...</div>}>
          <KetcherEditor onReady={onReady} onError={(m) => setMsg(m)} />
        </Suspense>
      </div>
      <div className="draw-actions">
        <button type="button" className="primary" onClick={() => void build()} disabled={!ready || loading}>
          {loading ? 'Building...' : 'Build 3D'}
        </button>
        <button type="button" onClick={() => void handle.current?.clear()} disabled={!ready}>Clear</button>
        <span className="muted small">Use the wedge or hash bond tool to set stereocentres.</span>
        {msg && <span className="hint-bad small">{msg}</span>}
      </div>
    </div>
  )
}
