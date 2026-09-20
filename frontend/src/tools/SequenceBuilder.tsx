import { useState, type FormEvent } from 'react'
import { ApiError } from '../api'
import { toolsApi } from './api'
import type { SequenceKind, SequenceResult } from './types'

interface Props {
  onBuild: (smiles: string) => void
  loading: boolean
}

const KINDS: { id: SequenceKind; label: string; hint: string; example: string }[] = [
  { id: 'peptide', label: 'Peptide (L)', hint: 'One-letter (AGSK) or three-letter (Ala-Gly-Ser) codes, N to C terminus', example: 'Tyr-Gly-Gly-Phe-Met' },
  { id: 'd-peptide', label: 'Peptide (D)', hint: 'Same codes, all residues as D-amino acids', example: 'AGSK' },
  { id: 'dna', label: 'DNA', hint: "A, C, G, T written 5' to 3'", example: 'ACGT' },
  { id: 'rna', label: 'RNA', hint: "A, C, G, U written 5' to 3'", example: 'ACGU' },
  { id: 'helm', label: 'HELM', hint: 'HELM notation, e.g. PEPTIDE1{A.G.S}$$$$', example: 'PEPTIDE1{A.G.S}$$$$' },
]

/** Peptide / nucleotide sequence to structure; hands the SMILES to the normal build. */
export function SequenceBuilder({ onBuild, loading }: Props) {
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState<SequenceKind>('peptide')
  const [seq, setSeq] = useState('')
  const [preview, setPreview] = useState<SequenceResult | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const info = KINDS.find((k) => k.id === kind)!

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!seq.trim()) return
    setBusy(true)
    setErr(null)
    try {
      const r = await toolsApi.sequence(kind, seq)
      setPreview(r)
      onBuild(r.smiles)
    } catch (ex) {
      setPreview(null)
      setErr(ex instanceof ApiError ? ex.message : 'Could not build the sequence.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="seq-builder">
      <button type="button" className="link small" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? 'Hide' : 'Build from a'} peptide or nucleotide sequence
      </button>
      {open && (
        <form className="seq-form" onSubmit={(e) => void submit(e)}>
          <select value={kind} onChange={(e) => { setKind(e.target.value as SequenceKind); setPreview(null); setErr(null) }} aria-label="Sequence type">
            {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
          </select>
          <input value={seq} onChange={(e) => setSeq(e.target.value)} placeholder={info.example} aria-label="Sequence" spellCheck={false} />
          <button type="submit" className="primary" disabled={busy || loading || !seq.trim()}>{busy ? 'Building...' : 'Build'}</button>
          <button type="button" onClick={() => setSeq(info.example)}>Example</button>
          <p className="hint">{info.hint}. Up to about 18 amino acids or 7 nucleotides (150 heavy atoms).</p>
          {err && <p className="hint hint-bad">{err}</p>}
          {preview && (
            <p className="hint">
              {preview.residues !== null && <>{preview.residues} residue{preview.residues === 1 ? '' : 's'}, </>}
              {preview.formula}, {preview.mw.toFixed(1)} g/mol, {preview.heavy_atoms} heavy atoms.
            </p>
          )}
        </form>
      )}
    </div>
  )
}
