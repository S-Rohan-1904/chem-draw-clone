import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Molecule, NameLookup as Lookup } from '../types'

interface Props {
  mol: Molecule
  onUse: (name: string) => void
}

export function NameLookup({ mol, onUse }: Props) {
  const [state, setState] = useState<'idle' | 'busy' | 'done' | 'error'>('idle')
  const [result, setResult] = useState<Lookup | null>(null)

  useEffect(() => {
    setState('idle')
    setResult(null)
  }, [mol.inchikey])

  const run = async () => {
    setState('busy')
    try {
      setResult(await api.lookupName(mol.inchikey))
      setState('done')
    } catch {
      setState('error')
    }
  }

  if (state === 'idle') {
    return <button type="button" onClick={() => void run()} title="Ask PubChem for this structure's name (needs internet)">Look up name</button>
  }
  if (state === 'busy') return <span className="muted small">Looking up...</span>
  if (state === 'error') return <span className="hint-bad small">Lookup failed (offline?)</span>
  if (!result?.found) return <span className="muted small">Not in PubChem</span>
  return (
    <span className="lookup-result">
      {result.title && <b>{result.title}</b>}
      {result.iupac && (
        <>
          {result.title ? ' · ' : ''}
          <span>{result.iupac}</span>{' '}
          <button type="button" className="link" onClick={() => onUse(result.iupac as string)}>Use as input</button>
        </>
      )}
      {result.cid && (
        <a className="small muted" href={`https://pubchem.ncbi.nlm.nih.gov/compound/${result.cid}`} target="_blank" rel="noreferrer"> PubChem</a>
      )}
    </span>
  )
}
