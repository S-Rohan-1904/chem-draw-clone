"""Build the reaction index (reactions.db) from Daniel Lowe's USPTO reaction set.

Source: Lowe, D. (2017) Chemical reactions from US patents (1976-Sep2016),
figshare, https://doi.org/10.6084/m9.figshare.5104873, CC0. Use the grants
file 1976_Sep2016_USPTOgrants_smiles.rsmi (tab separated: ReactionSmiles,
PatentNumber, ParagraphNum, Year, TextMinedYield, CalculatedYield). The
reaction SMILES are atom-mapped, which is what lets us tell the molecules that
end up in the product from solvents and reagents.

For every molecule the index keeps up to five reaction types in each
direction ("uses": the molecule is a reactant, "makes": it is the product),
ranked by how many distinct patent reactions show that type, each with one
real example (one with a reported yield, then the smallest, then best yield).

Runs once on a developer machine (a few minutes on 8 cores), not on the server.

Usage: uv run python scripts/build_reactions.py PATH.rsmi [--out reactions.db] [-j 8] [--limit N] [--max-atoms 60]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rdkit import Chem, RDLogger  # noqa: E402

from app.groups import find_groups  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SOURCE = "Lowe, Chemical reactions from US patents (1976-Sep2016), figshare, doi:10.6084/m9.figshare.5104873, CC0"
MAX_PRODUCT_ATOMS = 60
MAX_AGENTS = 5
TOP = 5


# --- one reaction ------------------------------------------------------------

def _yield(*fields: str) -> float | None:
    best = None
    for f in fields:
        try:
            v = float(f.strip().rstrip("%"))
        except (ValueError, AttributeError):
            continue
        if 0 < v <= 100 and (best is None or v > best):
            best = v
    return best


def _unmapped(mol: Chem.Mol) -> Chem.Mol:
    m = Chem.Mol(mol)
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    return m


def _canonical(mol: Chem.Mol) -> tuple[str, list[int]]:
    """Canonical SMILES and, for each atom index, its position in that SMILES."""
    smi = Chem.MolToSmiles(mol)
    order = list(mol.GetPropsAsDict(includePrivate=True, includeComputed=True)["_smilesAtomOutputOrder"])
    pos = [0] * mol.GetNumAtoms()
    for p, idx in enumerate(order):
        pos[idx] = p
    return smi, pos


def _neighbours(atom: Chem.Atom, keep: set[int]) -> list[tuple]:
    """What an atom is bonded to: map number (or element, for atoms that do not survive) and bond order."""
    out = []
    for b in atom.GetBonds():
        nb = b.GetOtherAtom(atom)
        m = nb.GetAtomMapNum()
        out.append((m if m in keep else "x" + nb.GetSymbol(), str(b.GetBondType())))
    return sorted(out, key=str)


def _pair(a: Chem.Atom, b: Chem.Atom) -> str:
    s1, s2 = sorted((a.GetSymbol(), b.GetSymbol()), key=lambda s: (s != "C", s))
    return f"{s1}-{s2}"


# Group names from groups.py that read oddly in a reaction label.
_DISPLAY = {"Aniline N": "Aryl amine"}


def _label(before: Counter, after: Counter, formed: Counter, broken: Counter) -> str:
    lost = [_DISPLAY.get(n, n) for n in before if before[n] > after[n]]
    gained = [_DISPLAY.get(n, n) for n in after if after[n] > before[n]]
    bond = ""
    if formed:
        bond = f"new {formed.most_common(1)[0][0]} bond"
    elif broken:
        bond = f"{broken.most_common(1)[0][0]} bond broken"
    if lost and gained:
        return f"{' + '.join(lost)} → {' + '.join(gained)}"
    if lost:
        return f"{' + '.join(lost)} → {bond}" if bond else f"{' + '.join(lost)} removed"
    if gained:
        return f"Forms {' + '.join(gained)}" + (f" ({bond})" if bond else "")
    return bond[:1].upper() + bond[1:] if bond else ""


def _groups_touching(mol: Chem.Mol, atoms: set[int]) -> Counter:
    """Functional groups that include a reacting atom. Aromatic rings are left out:
    a ring next to the reaction is not what changes."""
    c: Counter = Counter()
    for g in find_groups(mol):
        if g["name"] == "Aromatic ring":
            continue
        for match in g["atoms"]:
            if atoms.intersection(match):
                c[g["name"]] += 1
    return c


_key_cache: dict[str, str] = {}


def _inchikey(smiles: str, mol: Chem.Mol) -> str:
    key = _key_cache.get(smiles)
    if key is None:
        key = Chem.MolToInchiKey(mol) or ""
        if len(_key_cache) > 200_000:
            _key_cache.clear()
        _key_cache[smiles] = key
    return key


def _consistent_maps(left: list, right: list) -> bool:
    """Reject rows whose atom mapping cannot be right: a map number used twice on
    one side (the text-mining then stitches products from unrelated molecules),
    or a mapped atom that changes element."""
    elements: dict[int, int] = {}
    for side in (left, right):
        seen: set[int] = set()
        for m in side:
            if m is None:
                continue
            for a in m.GetAtoms():
                mp = a.GetAtomMapNum()
                if not mp:
                    continue
                if mp in seen:
                    return False
                seen.add(mp)
                if elements.setdefault(mp, a.GetAtomicNum()) != a.GetAtomicNum():
                    return False
    return True


def process_line(line: str, max_atoms: int = MAX_PRODUCT_ATOMS) -> dict | None:
    """One .rsmi row -> {rxn: (...), key: str, obs: [(inchikey, skeleton, smiles, heavy, direction, label, centre)]}."""
    fields = line.rstrip("\n").split("\t")
    if len(fields) < 4 or not fields[0] or fields[0] == "ReactionSmiles":
        return None
    parts = fields[0].split(" ")[0].split(">")
    if len(parts) != 3:
        return None
    patent = fields[1].strip()
    try:
        year = int(fields[3])
    except ValueError:
        year = 0
    yld = _yield(*(fields[4:6] if len(fields) >= 6 else []))

    left = [(s, Chem.MolFromSmiles(s)) for s in parts[0].split(".") if s]
    agents = [(s, Chem.MolFromSmiles(s)) for s in parts[1].split(".") if s]
    right_all = [Chem.MolFromSmiles(s) for s in parts[2].split(".") if s]
    if not _consistent_maps([m for _, m in left], right_all):
        return None
    right = [m for m in right_all if m is not None and any(a.GetAtomMapNum() for a in m.GetAtoms())]
    if not right:
        return None
    product = max(right, key=lambda m: m.GetNumHeavyAtoms())
    if product.GetNumHeavyAtoms() > MAX_PRODUCT_ATOMS:
        return None
    pmaps = {a.GetAtomMapNum() for a in product.GetAtoms() if a.GetAtomMapNum()}

    reactants, others = [], []
    for s, m in left:
        if m is not None and any(a.GetAtomMapNum() in pmaps for a in m.GetAtoms()):
            reactants.append(m)
        elif m is not None:
            others.append(m)
    if not reactants or len(reactants) > 4:
        return None
    rmaps = {a.GetAtomMapNum() for m in reactants for a in m.GetAtoms() if a.GetAtomMapNum() in pmaps}

    # Reaction centre: mapped atoms whose bonding, charge or H count changes.
    p_by_map = {a.GetAtomMapNum(): a for a in product.GetAtoms() if a.GetAtomMapNum()}
    centre_maps: set[int] = set()
    r_bonds: dict[frozenset, tuple[Chem.Atom, Chem.Atom]] = {}
    broken: Counter = Counter()
    for m in reactants:
        for a in m.GetAtoms():
            mp = a.GetAtomMapNum()
            if mp not in pmaps:
                continue
            pa = p_by_map[mp]
            if (_neighbours(a, pmaps) != _neighbours(pa, rmaps) or a.GetFormalCharge() != pa.GetFormalCharge()
                    or a.GetTotalNumHs() != pa.GetTotalNumHs()):
                centre_maps.add(mp)
            for b in a.GetBonds():
                nb = b.GetOtherAtom(a)
                if nb.GetAtomMapNum() in pmaps:
                    r_bonds[frozenset((mp, nb.GetAtomMapNum()))] = (a, nb)
                else:
                    broken[_pair(a, nb)] += 1  # bond to a leaving group
    if not centre_maps:
        return None
    formed: Counter = Counter()
    for b in product.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        k = frozenset((a1.GetAtomMapNum(), a2.GetAtomMapNum()))
        if k not in r_bonds and any(k):  # bonds inside unmapped fragments are not the reaction
            formed[_pair(a1, a2)] += 1
            centre_maps.update(x for x in k if x)
    p_bond_keys = {frozenset((b.GetBeginAtom().GetAtomMapNum(), b.GetEndAtom().GetAtomMapNum())) for b in product.GetBonds()}
    for k, (a, nb) in r_bonds.items():
        if k not in p_bond_keys:
            broken[_pair(a, nb)] += 1

    # Unmapped molecules for display, identity and group matching (atom indices are unchanged).
    plain_r = [_unmapped(m) for m in reactants]
    plain_p = _unmapped(product)
    r_smiles = [_canonical(m) for m in plain_r]
    p_smiles, p_pos = _canonical(plain_p)
    agent_smiles = []
    for _, m in agents + [(None, o) for o in others]:
        if m is not None:
            s = Chem.MolToSmiles(_unmapped(m))
            if s not in agent_smiles:
                agent_smiles.append(s)
    agent_smiles = agent_smiles[:MAX_AGENTS]
    if any(s == p_smiles for s, _ in r_smiles):
        return None  # product listed among the reactants: a mis-mapped or no-change entry
    rxn_smiles = f"{'.'.join(s for s, _ in r_smiles)}>{'.'.join(agent_smiles)}>{p_smiles}"
    key = f"{'.'.join(sorted(s for s, _ in r_smiles))}>>{p_smiles}"

    p_centre = {a.GetIdx() for a in product.GetAtoms() if a.GetAtomMapNum() in centre_maps or not a.GetAtomMapNum()}
    after_all = _groups_touching(plain_p, p_centre)
    obs = []
    before_all: Counter = Counter()
    for m, plain, (smi, pos) in zip(reactants, plain_r, r_smiles):
        centre = {a.GetIdx() for a in m.GetAtoms() if a.GetAtomMapNum() in centre_maps}
        before = _groups_touching(plain, centre)
        before_all += before
        if not centre or plain.GetNumHeavyAtoms() > max_atoms:
            continue
        # A molecule is "used" only if most of it ends up in the product; otherwise
        # the mapping credits it with a stray atom or two (seen with solvents).
        kept = sum(1 for a in m.GetAtoms() if a.GetAtomicNum() > 1 and a.GetAtomMapNum() in pmaps)
        if kept * 2 < plain.GetNumHeavyAtoms():
            continue
        mine = {a.GetAtomMapNum() for a in m.GetAtoms() if a.GetAtomMapNum() in centre_maps}
        p_mine = {a.GetIdx() for a in product.GetAtoms() if a.GetAtomMapNum() in mine}
        mine_formed: Counter = Counter()
        for b in product.GetBonds():
            a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
            if frozenset((a1.GetAtomMapNum(), a2.GetAtomMapNum())) not in r_bonds and (a1.GetIdx() in p_mine or a2.GetIdx() in p_mine):
                mine_formed[_pair(a1, a2)] += 1
        label = _label(before, _groups_touching(plain_p, p_mine), mine_formed, broken)
        if label:
            ik = _inchikey(smi, plain)
            if ik:
                obs.append((ik, ik[:14], smi, plain.GetNumHeavyAtoms(), "uses", label, ",".join(str(pos[i]) for i in sorted(centre))))
    if plain_p.GetNumHeavyAtoms() <= max_atoms:
        label = _label(before_all, after_all, formed, broken)
        ik = _inchikey(p_smiles, plain_p)
        if label and ik:
            obs.append((ik, ik[:14], p_smiles, plain_p.GetNumHeavyAtoms(), "makes", label, ",".join(str(p_pos[i]) for i in sorted(p_centre))))
    if not obs:
        return None
    size = sum(m.GetNumHeavyAtoms() for m in plain_r) + plain_p.GetNumHeavyAtoms()
    return {"rxn": (rxn_smiles, patent, year, yld), "size": size, "key": key, "obs": obs}


def _chunk(args: tuple[list[str], int]) -> list[dict]:
    lines, max_atoms = args
    out = []
    for line in lines:
        try:
            r = process_line(line, max_atoms)
        except Exception:  # noqa: BLE001 - one bad row must not stop the build
            r = None
        if r is not None:
            out.append(r)
    return out


# --- aggregation -----------------------------------------------------------

class Index:
    def __init__(self) -> None:
        self.seen: set[int] = set()
        self.rxns: list[tuple] = []
        self.sizes: list[int] = []  # heavy atoms in reactants + product, to prefer simple examples
        self.mols: dict[str, tuple[str, str]] = {}  # inchikey -> (skeleton, smiles)
        # (inchikey, direction, label) -> [count, rxn_id, centre]
        self.agg: dict[tuple[str, str, str], list] = {}
        self.stats = Counter()

    def add(self, r: dict) -> None:
        h = hash(r["key"])
        if h in self.seen:
            self.stats["duplicates"] += 1
            return
        self.seen.add(h)
        self.stats["reactions"] += 1
        rid = len(self.rxns)
        self.rxns.append(r["rxn"])
        self.sizes.append(r["size"])
        _, _, year, yld = r["rxn"]
        rank = (yld is not None, -r["size"], yld or 0, year)
        for ik, skel, smi, _heavy, direction, label, centre in r["obs"]:
            self.mols.setdefault(ik, (skel, smi))
            k = (ik, direction, label)
            cur = self.agg.get(k)
            if cur is None:
                self.agg[k] = [1, rid, centre]
                continue
            cur[0] += 1
            _, _, byear, byld = self.rxns[cur[1]]
            # Example: a reaction with a reported yield (a real worked example; text-mining
            # slips rarely carry one), then the simplest, then best yield, then most recent.
            if rank > (byld is not None, -self.sizes[cur[1]], byld or 0, byear):
                cur[1], cur[2] = rid, centre

    def write(self, out: Path) -> None:
        by_mol: dict[tuple[str, str], list] = defaultdict(list)
        for (ik, direction, label), (count, rid, centre) in self.agg.items():
            by_mol[(ik, direction)].append((count, label, rid, centre))
        if out.exists():
            out.unlink()
        db = sqlite3.connect(out)
        db.executescript(
            """
            CREATE TABLE mol (id INTEGER PRIMARY KEY, inchikey TEXT NOT NULL, skeleton TEXT NOT NULL, smiles TEXT NOT NULL);
            CREATE TABLE rxn (id INTEGER PRIMARY KEY, smiles TEXT NOT NULL, patent TEXT, year INTEGER, yield REAL);
            CREATE TABLE top (mol_id INTEGER NOT NULL, direction TEXT NOT NULL, rank INTEGER NOT NULL,
                              label TEXT NOT NULL, count INTEGER NOT NULL, rxn_id INTEGER NOT NULL, centre TEXT);
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
            """
        )
        mol_ids: dict[str, int] = {}
        rxn_ids: dict[int, int] = {}
        top_rows = []
        for (ik, direction), rows in by_mol.items():
            rows.sort(key=lambda r: (-r[0], r[1]))
            mid = mol_ids.get(ik)
            if mid is None:
                mid = mol_ids[ik] = len(mol_ids) + 1
            for rank, (count, label, rid, centre) in enumerate(rows[:TOP], 1):
                new = rxn_ids.get(rid)
                if new is None:
                    new = rxn_ids[rid] = len(rxn_ids) + 1
                top_rows.append((mid, direction, rank, label, count, new, centre))
        db.executemany("INSERT INTO mol VALUES (?,?,?,?)", ((mid, ik, *self.mols[ik]) for ik, mid in mol_ids.items()))
        db.executemany("INSERT INTO rxn VALUES (?,?,?,?,?)", ((new, *self.rxns[old]) for old, new in rxn_ids.items()))
        db.executemany("INSERT INTO top VALUES (?,?,?,?,?,?,?)", top_rows)
        db.executescript(
            """
            CREATE INDEX mol_key ON mol (inchikey);
            CREATE INDEX mol_skel ON mol (skeleton);
            CREATE INDEX top_mol ON top (mol_id, direction, rank);
            """
        )
        meta = {
            "source": SOURCE,
            "built": date.today().isoformat(),
            "reactions": str(self.stats["reactions"]),
            "duplicates_skipped": str(self.stats["duplicates"]),
            "rows_read": str(self.stats["rows"]),
            "molecules": str(len(mol_ids)),
            "examples": str(len(rxn_ids)),
        }
        db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
        db.commit()
        db.close()


def build(lines, out: Path, jobs: int = 1, max_atoms: int = MAX_PRODUCT_ATOMS, chunk: int = 2000) -> Index:
    index = Index()

    def batches():
        buf = []
        for line in lines:
            index.stats["rows"] += 1
            buf.append(line)
            if len(buf) >= chunk:
                yield (buf, max_atoms)
                buf = []
        if buf:
            yield (buf, max_atoms)

    if jobs > 1:
        with ProcessPoolExecutor(jobs) as pool:
            for i, results in enumerate(pool.map(_chunk, batches(), chunksize=1)):
                for r in results:
                    index.add(r)
                if i % 50 == 0:
                    print(f"  {index.stats['rows']:>9} rows, {index.stats['reactions']:>9} reactions", flush=True)
    else:
        for b in batches():
            for r in _chunk(b):
                index.add(r)
    index.write(out)
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rsmi", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "reactions.db")
    ap.add_argument("-j", "--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="read only the first N rows (for a trial run)")
    ap.add_argument("--max-atoms", type=int, default=MAX_PRODUCT_ATOMS, help="index molecules up to this many heavy atoms")
    args = ap.parse_args()

    t0 = time.time()
    with open(args.rsmi, encoding="utf-8", errors="replace") as f:
        lines = f if not args.limit else (line for _, line in zip(range(args.limit), f))
        index = build(lines, args.out, args.jobs, args.max_atoms)
    size = args.out.stat().st_size / 1e6
    print(f"{index.stats['rows']} rows -> {index.stats['reactions']} reactions "
          f"({index.stats['duplicates']} duplicates), {size:.1f} MB in {time.time() - t0:.0f} s -> {args.out}")


if __name__ == "__main__":
    main()
