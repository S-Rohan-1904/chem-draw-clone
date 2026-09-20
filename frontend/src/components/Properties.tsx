import { Fragment } from 'react'
import type { Molecule } from '../types'
import { Elemental } from '../tools/Elemental'

const ROWS: { key: keyof Molecule['properties']; label: string; hint: string; fmt?: (v: number) => string }[] = [
  { key: 'exact_mass', label: 'Exact mass', hint: 'Monoisotopic mass, Da', fmt: (v) => v.toFixed(4) },
  { key: 'logp', label: 'logP', hint: 'Octanol/water partition (Crippen)', fmt: (v) => v.toFixed(2) },
  { key: 'tpsa', label: 'TPSA', hint: 'Topological polar surface area, A\u00b2', fmt: (v) => v.toFixed(1) },
  { key: 'hbd', label: 'H-bond donors', hint: 'O-H and N-H groups' },
  { key: 'hba', label: 'H-bond acceptors', hint: 'N and O acceptor atoms' },
  { key: 'rotatable_bonds', label: 'Rotatable bonds', hint: 'Single bonds not in rings or to terminal atoms' },
  { key: 'heavy_atoms', label: 'Heavy atoms', hint: 'Atoms other than hydrogen' },
  { key: 'rings', label: 'Rings', hint: 'Smallest set of smallest rings' },
  { key: 'aromatic_rings', label: 'Aromatic rings', hint: '' },
  { key: 'stereocentres', label: 'Stereocentres', hint: 'Tetrahedral centres, specified or not' },
  { key: 'charge', label: 'Formal charge', hint: '' },
  { key: 'qed', label: 'QED', hint: 'Drug-likeness, 0 to 1', fmt: (v) => v.toFixed(2) },
]

export function Properties({ mol }: { mol: Molecule }) {
  const p = mol.properties
  const lip = p.lipinski_violations
  return (
    <section className="card">
      <header className="card-head">
        <h2>Properties</h2>
        <span className={`tag ${lip === 0 ? 'tag-ok' : 'tag-warn'}`} title="Rule of five: MW \u2264 500, logP \u2264 5, donors \u2264 5, acceptors \u2264 10">
          Lipinski: {lip === 0 ? 'passes' : `${lip} violation${lip > 1 ? 's' : ''}`}
        </span>
      </header>
      <dl className="props props-grid">
        <dt>Formula</dt><dd>{mol.formula}</dd>
        <dt>MW</dt><dd>{mol.mw.toFixed(2)} g/mol</dd>
        {ROWS.map((r) => (
          <Fragment key={r.key}>
            <dt title={r.hint}>{r.label}</dt>
            <dd>{r.fmt ? r.fmt(p[r.key]) : p[r.key]}</dd>
          </Fragment>
        ))}
      </dl>
      <Elemental smiles={mol.smiles} />
    </section>
  )
}
