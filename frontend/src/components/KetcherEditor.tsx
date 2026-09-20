import { useEffect, useRef } from 'react'
import { Editor } from 'ketcher-react'
import { StandaloneStructServiceProvider } from 'ketcher-standalone'
import type { Ketcher } from 'ketcher-core'
import 'ketcher-react/dist/index.css'

const provider = new StandaloneStructServiceProvider()

export interface EditorHandle {
  getMolfile: () => Promise<string>
  setMolecule: (struct: string) => Promise<void>
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
          getMolfile: () => k.getMolfile('v2000'),
          setMolecule: async (s) => {
            await k.setMolecule(s)
          },
          clear: async () => {
            await k.setMolecule('')
          },
        })
      }}
    />
  )
}
