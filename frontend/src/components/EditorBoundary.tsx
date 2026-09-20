import { Component, type ReactNode } from 'react'

interface State {
  error: string | null
}

const RELOAD_KEY = 'chem.editor-reloaded'

/** Keeps a failure inside the structure editor (a stale chunk after a
 * deploy, a WASM load error) from blanking the whole page. A failed chunk
 * load reloads the page once to pick up the current build. */
export class EditorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(e: unknown): State {
    return { error: e instanceof Error ? e.message : String(e) }
  }

  componentDidCatch(e: unknown) {
    const msg = e instanceof Error ? e.message : String(e)
    const stale = /Failed to fetch dynamically imported module|Loading chunk|Importing a module script failed|ChunkLoadError/i.test(msg)
    let reloaded = false
    try {
      reloaded = sessionStorage.getItem(RELOAD_KEY) === '1'
      if (stale && !reloaded) sessionStorage.setItem(RELOAD_KEY, '1')
    } catch {
      /* storage unavailable */
    }
    if (stale && !reloaded) window.location.reload()
  }

  render() {
    if (this.state.error) {
      return (
        <div className="editor-loading">
          <p className="error">The structure editor could not be loaded.</p>
          <p className="muted small">{this.state.error}</p>
          <button type="button" onClick={() => window.location.reload()}>Reload the page</button>
        </div>
      )
    }
    return this.props.children
  }
}
