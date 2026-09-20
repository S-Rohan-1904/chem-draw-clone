import { useEffect, useRef } from 'react'
import { Editor } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import type { Ketcher } from 'ketcher-core'
import 'ketcher-react/dist/index.css'

const provider = new StandaloneStructServiceProvider()

export interface EditorHandle {
  getMolfile: () => Promise<string>
  setMolecule: (struct: string) => Promise<void>
  /** Add a structure to the canvas next to what is already there. */
  addFragment: (struct: string) => Promise<void>
  clear: () => Promise<void>
}

interface Props {
  onReady: (h: EditorHandle) => void
  onError: (msg: string) => void
}

export default function KetcherEditor({ onReady, onError }: Props) {
  const ketcher = useRef<Ketcher | null>(null)

  useEffect(() => {
    return () => {
      ketcher.current = null
    }
  }, [])

  return (
    <Editor
      staticResourcesUrl=""
      structServiceProvider={provider}
      disableMacromoleculesEditor
      errorHandler={onError}
      onInit={(k) => {
        ketcher.current = k
        ;(window as unknown as { ketcher?: Ketcher }).ketcher = k
        onReady({
          getMolfile: () => k.getMolfile('v3000'), // V3000 carries enhanced stereo (ABS / AND / OR) marks
          setMolecule: async (s) => {
            await k.setMolecule(s)
            // onInit can fire for an instance Ketcher has already replaced
            // (StrictMode remounts): its setMolecule resolves but draws
            // nothing, and getSmiles throws. Fail so the caller retries on
            // the live instance.
            if (s && !(await k.getSmiles())) throw new Error('Editor not ready.')
          },
          addFragment: async (s) => {
            await k.addFragment(s)
          },
          clear: async () => {
            await k.setMolecule('')
          },
        })
      }}
    />
  )
}
