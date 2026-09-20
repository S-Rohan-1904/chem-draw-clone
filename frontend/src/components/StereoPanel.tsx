import type { Molecule, StereoExplanation } from '../types'

interface Props {
  mol: Molecule
  onHover: (atomIdx: number | null) => void
  onSelect: (sel: { atom_idx?: number; bond_idx?: number } | null) => void
  selected: string | null
  explanation: StereoExplanation | null
  onVariant: (op: 'mirror' | 'invert', atomIdx?: number) => void
}

export function StereoPanel({ mol, onHover, onSelect, selected, explanation, onVariant }: Props) {
  const { centers, double_bonds, unspecified } = mol.stereo
  const none = centers.length === 0 && double_bonds.length === 0
  return (
    <section className="card">
      <header className="card-head">
        <h2>Stereochemistry</h2>
        {centers.some((c) => c.label !== '?') && (
          <button type="button" onClick={() => onVariant('mirror')} title="Build the enantiomer and compare">Mirror image</button>
        )}
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
          <button
            type="button"
            key={`a${c.atom_idx}`}
            className={`chip ${c.label === '?' ? 'chip-warn' : 'chip-atom'} ${selected === `a${c.atom_idx}` ? 'active' : ''}`}
            onMouseEnter={() => onHover(c.atom_idx)}
            onMouseLeave={() => onHover(null)}
            onClick={() => (c.label === '?' ? undefined : onSelect(selected === `a${c.atom_idx}` ? null : { atom_idx: c.atom_idx }))}
            title={c.label === '?' ? `Atom ${c.atom_idx + 1}` : 'Click to see why'}
          >
            {c.symbol}&nbsp;{c.label}
          </button>
        ))}
        {double_bonds.map((b) => (
          <button
            type="button"
            key={`b${b.bond_idx}`}
            className={`chip ${b.label === '?' ? 'chip-warn' : 'chip-bond'} ${selected === `b${b.bond_idx}` ? 'active' : ''}`}
            onMouseEnter={() => onHover(b.atoms[0])}
            onMouseLeave={() => onHover(null)}
            onClick={() => (b.label === '?' ? undefined : onSelect(selected === `b${b.bond_idx}` ? null : { bond_idx: b.bond_idx }))}
            title={b.label === '?' ? `Atoms ${b.atoms[0] + 1}, ${b.atoms[1] + 1}` : 'Click to see why'}
          >
            C=C&nbsp;{b.label}
          </button>
        ))}
      </div>
      {explanation && (
        <div className="explain">
          <h3>Why {explanation.label}?</h3>
          {explanation.kind === 'centre' && explanation.priorities && (
            <ol className="prio">
              {explanation.priorities.map((p) => (
                <li key={p.priority}><b>{p.priority}</b> {p.group}</li>
              ))}
            </ol>
          )}
          {explanation.kind === 'bond' && explanation.ends && (
            <div className="prio-ends">
              {explanation.ends.map((e, i) => (
                <ol className="prio" key={e.atom_idx}>
                  <li className="muted">End {i === 0 ? 'a' : 'b'}</li>
                  {e.substituents.map((p) => (
                    <li key={p.priority}><b>{p.priority}{i === 0 ? 'a' : 'b'}</b> {p.group}</li>
                  ))}
                </ol>
              ))}
            </div>
          )}
          <ol className="steps">
            {explanation.steps.map((st) => <li key={st}>{st}</li>)}
          </ol>
          {explanation.kind === 'centre' && (
            <button type="button" className="small-btn" onClick={() => onVariant('invert', explanation.atom_idx)}>
              Flip this centre and compare
            </button>
          )}
        </div>
      )}
      <dl className="props">
        <dt>Source</dt><dd>{mol.source === 'iupac' ? 'IUPAC name' : mol.source === 'molfile' ? 'Drawn structure' : 'SMILES'}</dd>
        <dt>SMILES</dt><dd><code>{mol.smiles}</code></dd>
        <dt>InChIKey</dt><dd><code>{mol.inchikey}</code></dd>
      </dl>
    </section>
  )
}
