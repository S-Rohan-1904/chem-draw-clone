import { useState } from 'react'
import { api } from '../api'
import type { Molecule } from '../types'

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function slug(text: string) {
  return text.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 60) || 'molecule'
}

export function Downloads({ mol }: { mol: Molecule }) {
  const [busy, setBusy] = useState(false)
  const base = slug(mol.input_text)
  return (
    <div className="downloads">
      <span className="muted">Download</span>
      <button type="button" onClick={() => download(new Blob([mol.svg], { type: 'image/svg+xml' }), `${base}.svg`)}>SVG (2D)</button>
      <button
        type="button"
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          try {
            download(await api.png(mol.smiles), `${base}.png`)
          } finally {
            setBusy(false)
          }
        }}
      >
        PNG (2D)
      </button>
      <button type="button" onClick={() => download(new Blob([mol.molblock], { type: 'chemical/x-mdl-molfile' }), `${base}.mol`)}>MOL (3D)</button>
      <button type="button" onClick={() => download(new Blob([mol.smiles + '\n'], { type: 'text/plain' }), `${base}.smi`)}>SMILES</button>
    </div>
  )
}
