import type { Molecule } from '../types'

interface Props {
  mol: Molecule
  onHover: (atomIdx: number | null) => void
}

export function StereoPanel({ mol, onHover }: Props) {
  const { centers, double_bonds, unspecified } = mol.stereo
  const none = centers.length === 0 && double_bonds.length === 0
  return (
    <section className="card">
      <header className="card-head">
        <h2>Stereochemistry</h2>
      </header>
      {none && <p className="muted">None</p>}
      {unspecified && (
        <p className="warn">
          Unspecified stereocentres marked <b>?</b>.{' '}
          {mol.source === 'molfile' ? 'Use a wedge or hash bond to set them.' : 'Add descriptors to the name, e.g. (2R) or (E).'}
        </p>
      )}
      <div className="chips">
        {centers.map((c) => (
          <span
            key={`a${c.atom_idx}`}
            className={`chip ${c.label === '?' ? 'chip-warn' : 'chip-atom'}`}
            onMouseEnter={() => onHover(c.atom_idx)}
            onMouseLeave={() => onHover(null)}
            title={`Atom ${c.atom_idx + 1}`}
          >
            {c.symbol}&nbsp;{c.label}
          </span>
        ))}
        {double_bonds.map((b) => (
          <span
            key={`b${b.bond_idx}`}
            className={`chip ${b.label === '?' ? 'chip-warn' : 'chip-bond'}`}
            onMouseEnter={() => onHover(b.atoms[0])}
            onMouseLeave={() => onHover(null)}
            title={`Atoms ${b.atoms[0] + 1}, ${b.atoms[1] + 1}`}
          >
            C=C&nbsp;{b.label}
          </span>
        ))}
      </div>
      <dl className="props">
        <dt>Source</dt><dd>{mol.source === 'iupac' ? 'IUPAC name' : mol.source === 'molfile' ? 'Drawn structure' : 'SMILES'}</dd>
        <dt>SMILES</dt><dd><code>{mol.smiles}</code></dd>
        <dt>Formula</dt><dd>{mol.formula}</dd>
        <dt>MW</dt><dd>{mol.mw.toFixed(2)} g/mol</dd>
        <dt>InChIKey</dt><dd><code>{mol.inchikey}</code></dd>
      </dl>
    </section>
  )
}
