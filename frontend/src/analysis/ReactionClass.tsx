import { useEffect, useState } from 'react'
import type { ReactionResult } from '../types'
import { analysisApi } from './api'
import type { ReactionClass as Data } from './types'

/** Names the reaction shown in the Reaction card. */
export function ReactionClass({ rxn }: { rxn: ReactionResult }) {
  const [data, setData] = useState<Data | null>(null)
  useEffect(() => {
    setData(null)
    analysisApi.classify(rxn.reactants.map((m) => m.smiles), rxn.products.map((m) => m.smiles)).then(setData).catch(() => setData(null))
  }, [rxn])
  if (!data) return null
  return (
    <div className="rxn-class">
      {data.matches.length > 0 ? (
        <>
          <p><b>Recognised as: {data.matches[0].name}</b> <span className="muted small">(typical reagents: {data.matches[0].reagents})</span></p>
          {data.matches[0].explanation && <p className="small">{data.matches[0].explanation}</p>}
          {data.matches[0].mechanism_note && <p className="small">{data.matches[0].mechanism_note}</p>}
          {data.matches[0].note && <p className="muted small">{data.matches[0].note}</p>}
          {data.matches.length > 1 && <p className="muted small">Also fits: {data.matches.slice(1).map((m) => m.name).join('; ')}.</p>}
        </>
      ) : (
        <p><b>{data.guess}</b></p>
      )}
      {(data.groups_lost.length > 0 || data.groups_gained.length > 0) && (
        <p className="muted small">
          {data.groups_lost.length > 0 && <span>Groups lost: {data.groups_lost.join(', ')}. </span>}
          {data.groups_gained.length > 0 && <span>Groups gained: {data.groups_gained.join(', ')}.</span>}
        </p>
      )}
    </div>
  )
}
