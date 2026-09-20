import { useEffect, useState } from 'react'
import type { Molecule } from '../types'
import { analysisApi } from './api'
import type { SugarProjections as Data } from './types'

interface Props {
  mol: Molecule
  onHighlight: (atoms: number[] | null, colour?: string) => void
}

export function SugarProjections({ mol, onHighlight }: Props) {
  const [data, setData] = useState<Data | null>(null)
  const [tab, setTab] = useState<'fischer' | 'haworth'>('fischer')

  useEffect(() => {
    setData(null)
    analysisApi.sugars(mol.smiles).then((d) => {
      setData(d)
      setTab(d.fischer ? 'fischer' : 'haworth')
    }).catch(() => setData(null))
  }, [mol.smiles])

  if (!data || (!data.fischer && !data.haworth)) return null
  const f = data.fischer
  const h = data.haworth
  const sym = (i: number) => `${mol.atoms?.[i]?.symbol ?? ''}${i + 1}`

  return (
    <section className="card">
      <header className="card-head">
        <h2>Fischer and Haworth</h2>
        <div className="toolbar">
          {f && <button type="button" className={tab === 'fischer' ? 'active' : ''} onClick={() => setTab('fischer')}>Fischer</button>}
          {h && <button type="button" className={tab === 'haworth' ? 'active' : ''} onClick={() => setTab('haworth')}>Haworth</button>}
        </div>
      </header>
      {tab === 'fischer' && f && (
        <div className="bonding-split">
          <div className="svg-wrap bonding-svg" onMouseEnter={() => onHighlight(f.chain, '#f59e0b')} onMouseLeave={() => onHighlight(null)} dangerouslySetInnerHTML={{ __html: f.svg }} />
          <div>
            {f.dl && <p className="bonding-title"><span className="tag chir-meso">{f.dl} series</span> {f.dl_reason}</p>}
            {!f.dl && <p className="muted small">D/L is only assigned for sugars and amino acids: a carbonyl or carboxyl on top and a heteroatom on the deciding centre.</p>}
            <table className="bonding-table">
              <thead><tr><th>Carbon</th><th>Left</th><th>Right</th></tr></thead>
              <tbody>
                {f.rows.map((r, k) => (
                  <tr key={r.idx} onMouseEnter={() => onHighlight([r.idx, ...(r.left ? [r.left.idx] : []), ...(r.right ? [r.right.idx] : [])], '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
                    <td>C{k + 1} <span className="muted small">({sym(r.idx)})</span></td>
                    {r.kind === 'end' ? <td colSpan={2}>{r.label}</td> : (
                      <>
                        <td>{r.left?.text ?? ''}</td>
                        <td>{r.right?.text ?? ''}{r.kind === 'mid' ? <span className="muted small"> (not a stereocentre)</span> : null}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">Vertical bonds point away from you, horizontal bonds towards you. The most oxidised carbon is on top. Left and right are read from the 3D model, so they match the descriptors in the name.</p>
          </div>
        </div>
      )}
      {tab === 'haworth' && h && (
        <div className="bonding-split">
          <div className="svg-wrap bonding-svg" onMouseEnter={() => onHighlight([...h.ring, h.oxygen], '#f59e0b')} onMouseLeave={() => onHighlight(null)} dangerouslySetInnerHTML={{ __html: h.svg }} />
          <div>
            <p className="bonding-title">
              {h.anomer && <span className="tag chir-meso">{h.anomer === 'alpha' ? 'α' : 'β'} anomer</span>}
              {h.dl && <span className="tag chir-chiral">{h.dl} series</span>}
              <span className="tag">{h.kind}</span>
            </p>
            {h.anomer && h.reference && (
              <p>
                The anomeric group on C{h.atoms[0].label} points {h.anomeric_up ? 'up' : 'down'}; the reference group {h.reference.text} on C{h.reference.num} points {h.reference.up ? 'up' : 'down'}.
                {h.anomer === 'beta' ? ' Same side: β.' : ' Opposite sides: α.'}
              </p>
            )}
            <table className="bonding-table">
              <thead><tr><th>Ring carbon</th><th>Up</th><th>Down</th></tr></thead>
              <tbody>
                {h.atoms.map((a) => (
                  <tr key={a.idx} onMouseEnter={() => onHighlight([a.idx, ...a.subs.filter((s) => !s.h).map((s) => s.idx)], '#f59e0b')} onMouseLeave={() => onHighlight(null)}>
                    <td>C{a.label} <span className="muted small">({sym(a.idx)})</span></td>
                    <td>{a.subs.filter((s) => s.up).map((s) => s.text).join(', ')}</td>
                    <td>{a.subs.filter((s) => !s.up).map((s) => s.text).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {h.rings_available > 1 && <p className="muted small">Only the first sugar ring is drawn.</p>}
            <p className="muted small">The thick edge is nearest to you. Up and down come from which side of the ring plane each group sits on in the 3D model. In the D series, α has the anomeric group down.</p>
          </div>
        </div>
      )}
    </section>
  )
}
