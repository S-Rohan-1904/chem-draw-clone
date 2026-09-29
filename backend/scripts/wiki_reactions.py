"""Reactions written as equations in English Wikipedia chemical compound articles.

Articles give the textbook routes to a compound as equations, for example
{{chem2|C2H4 + H2O -> C2H5OH}} under Production in "Ethanol". This script
turns those equations into reaction SMILES that the index builder can use, and
keeps only the ones it can resolve without guessing:

- every species is a formula (or a link) that matches exactly one known
  structure: the compounds whose articles are linked from the same article,
  the article's own compound, or a small table of common reagents;
- the equation balances atom for atom with the written coefficients.

Steps (output files go in DIR):

  uv run python scripts/wiki_reactions.py fetch DIR      # compound list from Wikidata, wikitext of each article
  uv run python scripts/wiki_reactions.py extract DIR    # DIR/wiki_reactions.tsv and a report

The tsv has one reaction per line, reactants>>products, then the article title
and revision id, the equation or sentence as written, and the SMILES of the
article's compound. Atom-map it with
map_reactions.py (source wiki) before building the index.

Text of Wikipedia is CC BY-SA 4.0; each reaction is credited to its article.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

UA = {"User-Agent": "ChemIllustrator/1.0 (https://github.com/S-Rohan-1904/chem-draw-clone; reaction index builder)"}
SPARQL = "https://query.wikidata.org/sparql"
API = "https://en.wikipedia.org/w/api.php"
COMPOUNDS_QUERY = """SELECT ?t ?smi ?iso ?key WHERE {
  ?i wdt:P235 ?key . ?a schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?t .
  OPTIONAL { ?i wdt:P233 ?smi } OPTIONAL { ?i wdt:P2017 ?iso } }"""

# Species that equations write by formula without linking them. Only unambiguous formulas.
REAGENTS = {
    "H2": "[H][H]", "O2": "O=O", "N2": "N#N", "Cl2": "ClCl", "Br2": "BrBr", "I2": "II", "F2": "FF",
    "H2O": "O", "H2O2": "OO", "NH3": "N", "HCl": "Cl", "HBr": "Br", "HI": "I", "HF": "F", "HCN": "C#N",
    "CO": "[C-]#[O+]", "CO2": "O=C=O", "SO2": "O=S=O", "SO3": "O=S(=O)=O", "NO": "[N]=O", "NO2": "O=[N+][O-]",
    "N2O": "[N-]=[N+]=O", "H2S": "S", "H2SO4": "O=S(=O)(O)O", "HNO3": "O=[N+]([O-])O", "HNO2": "O=NO",
    "H3PO4": "O=P(O)(O)O", "NaOH": "[Na+].[OH-]", "KOH": "[K+].[OH-]", "LiOH": "[Li+].[OH-]",
    "NaCl": "[Na+].[Cl-]", "KCl": "[K+].[Cl-]", "NaBr": "[Na+].[Br-]", "KBr": "[K+].[Br-]", "NaI": "[Na+].[I-]",
    "NaHCO3": "[Na+].OC([O-])=O", "Na2CO3": "[Na+].[Na+].[O-]C([O-])=O", "NaNO2": "[Na+].[O-]N=O",
    "NaCN": "[Na+].[C-]#N", "KCN": "[K+].[C-]#N", "PCl3": "ClP(Cl)Cl", "PCl5": "ClP(Cl)(Cl)(Cl)Cl",
    "POCl3": "O=P(Cl)(Cl)Cl", "SOCl2": "O=S(Cl)Cl", "CH4": "C", "CH3OH": "CO", "HCHO": "C=O", "CH2O": "C=O",
    "HCOOH": "OC=O", "HCO2H": "OC=O", "C2H2": "C#C", "C2H4": "C=C", "C2H6": "CC", "CS2": "S=C=S",
    "COCl2": "O=C(Cl)Cl", "NaNH2": "[Na+].[NH2-]", "LiAlH4": "[Li+].[AlH4-]", "NaBH4": "[Na+].[BH4-]",
    "NH4Cl": "[NH4+].[Cl-]", "Na": "[Na]", "K": "[K]", "Li": "[Li]", "Mg": "[Mg]", "Zn": "[Zn]", "C": "[C]",
    "S": "[S]", "HOCl": "OCl", "Cl2O": "ClOCl", "O3": "[O-][O+]=O", "BF3": "FB(F)F", "AlCl3": "Cl[Al](Cl)Cl",
}

ARROW = re.compile(r"\s*(?:→|->|&rarr;|⟶|<=>|⇌|<->|⇄)\s*")
EQUATION = re.compile(r"\{\{\s*chem2\s*\|(.*?)\}\}(?!\})|<chem>(.*?)</chem>|<ce>(.*?)</ce>", re.S | re.I)
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")


# --- fetch ------------------------------------------------------------------------

def fetch(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(timeout=120, headers=UA)
    comp = out / "compounds.csv"
    if not comp.exists():
        r = client.get(SPARQL, params={"query": COMPOUNDS_QUERY}, headers={"Accept": "text/csv"})
        r.raise_for_status()
        comp.write_text(r.text, encoding="utf-8")
    titles = sorted({row["t"] for row in csv.DictReader(open(comp, encoding="utf-8"))})
    pages = out / "pages.jsonl"
    done = set()
    if pages.exists():
        done = {json.loads(line)["title"] for line in open(pages, encoding="utf-8")}
    todo = [t for t in titles if t not in done]
    print(f"{len(titles)} articles, {len(todo)} to fetch", flush=True)
    with open(pages, "a", encoding="utf-8") as f:
        for i in range(0, len(todo), 50):
            chunk = todo[i:i + 50]
            for attempt in range(5):
                try:
                    r = client.get(API, params={"action": "query", "prop": "revisions", "rvprop": "content|ids", "rvslots": "main",
                                                "titles": "|".join(chunk), "redirects": 1, "format": "json", "formatversion": 2,
                                                "maxlag": 5})
                    r.raise_for_status()
                    q = r.json()["query"]
                    break
                except Exception:  # noqa: BLE001 - rate limit or lag; wait and retry
                    time.sleep(5 * (attempt + 1))
            else:
                print(f"  gave up on {chunk[0]}...", flush=True)
                continue
            back = {}
            for x in q.get("normalized", []) + q.get("redirects", []):
                back[x["to"]] = back.get(x["from"], x["from"])
            for p in q["pages"]:
                if "revisions" not in p:
                    continue
                rev = p["revisions"][0]
                title = back.get(p["title"], p["title"])
                f.write(json.dumps({"title": title, "page": p["title"], "revid": rev["revid"],
                                    "text": rev["slots"]["main"]["content"]}) + "\n")
            if i % 1000 == 0:
                print(f"  {i + len(chunk)} fetched", flush=True)
            time.sleep(0.5)


# --- formulas ---------------------------------------------------------------------

def formula_of(mol: Chem.Mol) -> Counter:
    m = Chem.AddHs(mol)
    c = Counter(a.GetSymbol() for a in m.GetAtoms())
    c["+"] = sum(a.GetFormalCharge() for a in m.GetAtoms())
    return c


def _clean(species: str) -> str:
    s = species.replace("\\d", "=").replace("\\t", "#")  # chem2 double and triple bonds
    s = re.sub(r"\\[sq]|\\\*|\\\(|\\\)", "", s)  # other chem2 bond marks
    s = re.sub(r"(?<=[A-Za-z0-9)\]])[-–—](?=[A-Z(\[])", "", s)  # a written single bond: BrCH2–CH2Br
    s = re.sub(r"\^\{?([^}\s]*)\}?", r"\1", s)  # mhchem superscripts
    s = re.sub(r"_\{?(\d+)\}?", r"\1", s)  # mhchem subscripts
    s = s.replace("−", "-").replace("·", ".").replace("{", "").replace("}", "")
    s = re.sub(r"\((?:s|l|g|aq|cat)\)", "", s)  # state symbols
    return s.strip()


def parse_formula(text: str) -> Counter | None:
    """Element counts (and net charge under '+') of a written formula like CH3CO2H, (CH3)2O or [NH4]+."""
    s = re.sub(r"[=#]", "", text.strip())  # bond marks do not change the formula
    charge = 0
    m = re.search(r"(?<=[\]\)A-Za-z0-9])(\d*)([+-])$", s)
    if m:
        charge = int(m.group(1) or 1) * (1 if m.group(2) == "+" else -1)
        s = s[: m.start()]

    def parse(i: int) -> tuple[Counter, int]:
        c: Counter = Counter()
        while i < len(s):
            ch = s[i]
            if ch in "([":
                sub, i = parse(i + 1)
                n = re.match(r"\d*", s[i:]).group()
                i += len(n)
                for k, v in sub.items():
                    c[k] += v * int(n or 1)
            elif ch in ")]":
                return c, i + 1
            else:
                mm = re.match(r"([A-Z][a-z]?)(\d*)", s[i:])
                if not mm:
                    raise ValueError(s)
                c[mm.group(1)] += int(mm.group(2) or 1)
                i += len(mm.group(0))
        return c, i

    try:
        c, i = parse(0)
    except (ValueError, RecursionError):
        return None
    if i < len(s) or not c:
        return None
    if charge:
        c["+"] = charge
    return c


def _key(c: Counter) -> tuple:
    return tuple(sorted((k, v) for k, v in c.items() if v))


# --- condensed formulas -------------------------------------------------------------
# CH3COOH, (CH3)2CO, CH2\dCHCH2Cl, C6H5CH(OH)CH3: a chain of atoms, each followed by its
# hydrogens, with groups in brackets hanging off the atom before them (or after them, when
# the formula starts with the group). Each atom after the first either continues the chain
# or hangs off the current chain atom; bonds are single unless marked or needed to fill
# valences. A formula is accepted only when exactly one structure fits.

VALENCE = {"C": 4, "N": 3, "O": 2, "S": 2, "B": 3, "Si": 4, "P": 3, "F": 1, "Cl": 1, "Br": 1, "I": 1}
# Groups written as one unit, each a placeholder character bonded through its first atom.
UNITS = {"§": "c1ccccc1", "¤": "[N+](=O)[O-]"}
EXPAND = [("C6H5", "§"), ("Ph", "§"), ("NO2", "¤"), ("C2H5", "CH2CH3"), ("Et", "CH2CH3"), ("Me", "CH3"),
          ("C3H7", "CH2CH2CH3"), ("C4H9", "CH2CH2CH2CH3")]
MAX_CONDENSED = 14  # heavy atoms; the search doubles with each


def _tokens(s: str) -> list | None:
    """Nested list of ('atom', element, hydrogens), ('bond', order), ('unit', char) and ('group', tokens, count)."""
    pos = 0

    def seq() -> list | None:
        nonlocal pos
        out = []
        while pos < len(s):
            ch = s[pos]
            if ch == "(":
                pos += 1
                inner = seq()
                if inner is None or pos >= len(s) or s[pos] != ")":
                    return None
                pos += 1
                n = re.match(r"\d*", s[pos:]).group()
                pos += len(n)
                out.append(("group", inner, int(n or 1)))
            elif ch == ")":
                return out
            elif ch in "=#":
                out.append(("bond", 2 if ch == "=" else 3))
                pos += 1
            elif ch in UNITS:
                out.append(("unit", ch))
                pos += 1
            else:
                m = re.match(r"([A-Z][a-z]?)(\d*)", s[pos:])
                if not m or (m.group(1) not in VALENCE and m.group(1) != "H"):
                    return None
                pos += len(m.group(0))
                el, n = m.group(1), int(m.group(2) or 1)
                if el == "H":
                    if out and out[-1][0] == "atom":
                        out[-1] = ("atom", out[-1][1], out[-1][2] + n)
                    else:
                        out.append(("lead_h", n))  # H2NCH2...: hydrogens before their atom
                    continue
                if n > 1 and VALENCE[el] > 1:
                    if el != "O" and el != "S":
                        return None  # C2, N2 inside a formula: order of atoms unknown
                    out.extend([("atom", el, 0)] * n)  # CO2, SO2: pendant or chain, decided below
                    continue
                out.extend([("atom", el, 0)] * n)
        return out

    toks = seq()
    return toks if toks is not None and pos == len(s) else None


def parse_condensed(text: str) -> str | None:
    s = re.sub(r"\\d", "=", re.sub(r"\\t", "#", re.sub(r"\\s", "", text)))
    s = re.sub(r"\\[a-z]", "", s)
    for a, b in EXPAND:
        s = s.replace(a, b)
    toks = _tokens(s)
    if not toks:
        return None
    found: set[str] = set()
    n_choices = None
    mask = 0
    while n_choices is None or mask < (1 << n_choices):
        laid = _lay_out(toks, mask)
        if laid is None:
            return None
        atoms, edges, n = laid
        if n_choices is None:
            n_choices = n
            if n > 10 or len(atoms) > MAX_CONDENSED:
                return None
        smi = _build(atoms, edges)
        if smi:
            found.add(smi)
            if len(found) > 1:
                return None
        mask += 1
    return found.pop() if len(found) == 1 else None


def _lay_out(toks: list, mask: int) -> tuple[list, list, int] | None:
    """Atoms [(element, hydrogens)] and bonds [(a, b, order or 0)] for one set of choices:
    bit k of mask set means the k-th free atom hangs off the chain instead of continuing it."""
    atoms: list[tuple[str, int]] = []
    edges: list[tuple[int, int, int]] = []
    k = 0

    def run(seq: list, anchor: int | None) -> int | None:
        """Lays out seq hanging from anchor; returns the chain atom it ends on, or None."""
        nonlocal k
        current, pending, lead_h, leading, first = anchor, 0, 0, [], True
        for tok in seq:
            if tok[0] == "bond":
                pending = tok[1]
                continue
            if tok[0] == "lead_h":
                lead_h += tok[1]
                continue
            if tok[0] == "group":
                if current is None:
                    leading.append(tok)
                else:
                    for _ in range(tok[2]):
                        if run(tok[1], current) is None:
                            return None
                continue
            new = len(atoms)
            atoms.append((tok[1], 0) if tok[0] == "unit" else (tok[1], tok[2] + lead_h))
            lead_h = 0
            if current is None:
                current = new
            else:
                edges.append((current, new, pending))
                mono = atoms[new][0] not in UNITS and VALENCE[atoms[new][0]] == 1
                cur_mono = atoms[current][0] not in UNITS and VALENCE[atoms[current][0]] == 1
                if cur_mono or (first and anchor is not None):
                    current = new  # after a leading halogen, or a bracket group's own first atom
                elif not mono:
                    if not (mask >> k & 1):
                        current = new
                    k += 1
            pending = 0
            if first:
                first = False
                for g in leading:  # (CH3CO)2O: each copy bonds through the atom it ends on
                    for _ in range(g[2]):
                        end = run(g[1], None)
                        if end is None:
                            return None
                        edges.append((end, new, 0))
                leading = []
        return current if not leading and pending == 0 and lead_h == 0 and current is not None else None

    if run(toks, None) is None:
        return None
    return atoms, edges, k


def _build(atoms: list, bonds: list) -> str | None:
    """Molecule from atoms and bonds, raising bond orders so every valence is filled; one answer or None."""
    rw = Chem.RWMol()
    idx = []
    for el, h in atoms:
        if el in UNITS:
            unit = Chem.MolFromSmiles(UNITS[el])
            first = rw.GetNumAtoms()
            for a in unit.GetAtoms():
                rw.AddAtom(a)
            for b in unit.GetBonds():
                rw.AddBond(first + b.GetBeginAtomIdx(), first + b.GetEndAtomIdx(), b.GetBondType())
            idx.append(first)
        else:
            a = Chem.Atom(el)
            a.SetNumExplicitHs(h)
            a.SetNoImplicit(True)
            idx.append(rw.AddAtom(a))
    edges = [(idx[a], idx[b], order) for a, b, order in bonds]
    # Free valence per atom (the phenyl carbon has one).
    free = {}
    for i, (el, h) in enumerate(atoms):
        free[idx[i]] = 1 if el in UNITS else VALENCE[el] - h
    for a, b, fixed in edges:
        free[a] -= fixed or 1
        free[b] -= fixed or 1
    if any(v < 0 for v in free.values()):
        return None
    raisable = [k for k, (a, b, fixed) in enumerate(edges) if not fixed]
    sols = []

    def search(k: int, orders: dict) -> None:
        if len(sols) > 1:
            return
        if k == len(raisable):
            if all(v == 0 for v in free.values()):
                sols.append(dict(orders))
            return
        a, b, _ = edges[raisable[k]]
        for extra in (0, 1, 2):
            if free[a] >= extra and free[b] >= extra:
                free[a] -= extra
                free[b] -= extra
                orders[raisable[k]] = 1 + extra
                search(k + 1, orders)
                free[a] += extra
                free[b] += extra
        orders.pop(raisable[k], None)

    search(0, {})
    if len(sols) != 1:
        return None
    types = {1: Chem.BondType.SINGLE, 2: Chem.BondType.DOUBLE, 3: Chem.BondType.TRIPLE}
    for k, (a, b, fixed) in enumerate(edges):
        rw.AddBond(a, b, types[fixed or sols[0].get(k, 1)])
    try:
        m = rw.GetMol()
        Chem.SanitizeMol(m)
    except Exception:  # noqa: BLE001
        return None
    if any(a.GetNumRadicalElectrons() for a in m.GetAtoms()):
        return None
    return Chem.MolToSmiles(m)


# --- extract ----------------------------------------------------------------------

class Structures:
    """Title -> SMILES from Wikidata, and formula -> structures for resolving species."""

    def __init__(self, compounds: Path | None = None):
        self.by_title: dict[str, str] = {}
        for row in csv.DictReader(open(compounds, encoding="utf-8")) if compounds else []:
            smi = row["iso"] or row["smi"]
            if smi and row["t"] not in self.by_title:
                self.by_title[row["t"]] = smi
        self._formula: dict[str, Counter | None] = {}
        self._mol: dict[str, Chem.Mol | None] = {}

    def mol(self, smi: str) -> Chem.Mol | None:
        if smi not in self._mol:
            self._mol[smi] = Chem.MolFromSmiles(smi)
        return self._mol[smi]

    def formula(self, smi: str) -> Counter | None:
        if smi not in self._formula:
            m = self.mol(smi)
            self._formula[smi] = formula_of(m) if m is not None else None
        return self._formula[smi]


def _canon(smi: str) -> str:
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToSmiles(m) if m is not None else ""


def resolve(species: str, candidates: dict[str, str], st: Structures) -> tuple[int, str] | None:
    """(coefficient, SMILES) of one written species, or None when it is not certain."""
    sp = species.strip()
    m = re.match(r"^(\d+(?:\.\d+)?|½)\s*(?=\S)", sp)
    coef = 1
    if m and not re.match(r"^\d+[A-Z]?[a-z]?\d", sp[m.end():m.end()]):
        try:
            coef = int(m.group(1)) if m.group(1) != "½" else 0
        except ValueError:
            return None
        sp = sp[m.end():].strip()
    if coef <= 0:
        return None
    # A link names the compound outright: [[hydrochloric acid|HCl]].
    link = LINK.fullmatch(sp)
    if link:
        target = link.group(1).strip()
        target = target[0].upper() + target[1:]
        smi = st.by_title.get(target)
        if smi and st.formula(smi) is not None:
            return coef, smi
        sp = link.group(2) or link.group(1)
    sp = _clean(sp)
    if not sp or re.search(r"[a-z]{3,}|[*R]\b|R\d?\b|\bAr\b|\bX\b|e-", sp):
        return None  # a name, a generic group or an electron
    written = parse_formula(sp)
    if written is None:
        return None
    if sp in REAGENTS:
        return coef, REAGENTS[sp]
    condensed = parse_condensed(sp)
    if condensed and _key(formula_of(Chem.MolFromSmiles(condensed))) == _key(written):
        return coef, condensed
    hits = {_canon(s) for s in candidates.values() if st.formula(s) is not None and _key(st.formula(s)) == _key(written)}
    hits.discard("")
    if len(hits) == 1:
        return coef, hits.pop()
    return None


def balanced(side_l: list[tuple[int, str]], side_r: list[tuple[int, str]], st: Structures) -> bool:
    def total(side):
        c: Counter = Counter()
        for n, smi in side:
            for k, v in st.formula(smi).items():
                c[k] += n * v
        return _key(c)
    return total(side_l) == total(side_r)


def equations(text: str):
    for m in EQUATION.finditer(text):
        e = next(g for g in m.groups() if g is not None)
        if m.group(1) is not None:
            e = re.sub(r"\|\s*\w+\s*=.*$", "", e, flags=re.S)  # template options: |link=yes, |auto=1
        e = re.sub(r"<[^>]+>", "", e)
        if ARROW.search(e) and len(e) < 400:
            yield e.strip()


def _plain(text: str) -> str:
    """Wiki markup of a formula line as plain text: C<sub>4</sub>H<sub>9</sub>OH, CH{{sub|2}}, {{chem|C|4|H|9|Cl}}."""
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", text, flags=re.S)
    s = re.sub(r"\{\{\s*chem\s*\|([^{}]*)\}\}", lambda m: "".join(p for p in m.group(1).split("|") if "=" not in p), s)
    s = re.sub(r"\{\{\s*su[bp]\s*\|([^{}|]*)\}\}", r"\1", s)
    s = re.sub(r"</?su[bp]>", "", s)
    s = re.sub(r"'{2,}", "", s).replace("&nbsp;", " ").replace("&rarr;", "→")
    return s


def plain_equations(text: str):
    """Equations on their own indented line without the chem2 template: ': C4H9OH + HCl → C4H9Cl + H2O'."""
    for line in text.splitlines():
        if not line.startswith(":") or "{{chem2" in line or "<chem>" in line or "<math" in line:
            continue
        e = _plain(line.lstrip(":").strip()).rstrip(" .,;")
        if ARROW.search(e) and "+" in e and len(e) < 300 and "{{" not in e:
            yield e


# --- sentences -------------------------------------------------------------------
# "1-Bromobutane can also be prepared from [[butanol]] by treatment with [[hydrobromic acid]]."
# The compounds a preparation sentence names are the candidate starting materials of the
# article's compound. A candidate reaction is kept only when some of them, with small whole
# number amounts, give the compound plus at most two simple side products, atom for atom.

PREP_SECTION = re.compile(r"^(={2,4})\s*([^=]*?(?:Production|Preparation|Synthesis|Manufactur|Laboratory|Industrial|"
                          r"Occurrence and production|Formation)[^=]*?)\s*\1\s*$", re.M | re.I)
PREP_VERB = re.compile(r"\b(prepared|produced|synthesi[sz]ed|manufactured|obtained|made|formed|generated|"
                       r"treat(?:ing|ment)|reaction of|reacting|addition of|hydrogenation|dehydration|hydration|"
                       r"hydrolysis|chlorination|bromination|nitration|oxidation|reduction|esterification|"
                       r"condensation of|heating)\b", re.I)
# Reagents named in words that have no compound entry of their own (solutions), or whose entry
# is the element rather than the molecule that reacts.
NAMED = {"hydrochloric acid": "Cl", "hydrobromic acid": "Br", "hydroiodic acid": "I", "hydrofluoric acid": "F",
         "aqueous ammonia": "N", "ammonia water": "N", "caustic soda": "[Na+].[OH-]", "caustic potash": "[K+].[OH-]",
         "bleach": "[Na+].[O-]Cl", "hydrogen": "[H][H]", "chlorine": "ClCl", "bromine": "BrBr", "iodine": "II",
         "fluorine": "FF", "oxygen": "O=O", "nitrogen": "N#N", "water": "O", "steam": "O", "ozone": "[O-][O+]=O"}
# Reagents a process word implies without naming them.
IMPLIED = {"hydrogenat": "[H][H]", "hydrat": "O", "hydroly": "O", "chlorinat": "ClCl", "brominat": "BrBr",
           "nitrat": "O=[N+]([O-])O", "iodinat": "II"}
# Only side products a textbook would leave unnamed; anything else must be written in the article.
SIDE_PRODUCTS = ["O", "Cl", "Br", "I", "F", "N", "[Na+].[Cl-]", "[Na+].[Br-]", "[K+].[Cl-]", "[K+].[Br-]"]
ISOMERISE = re.compile(r"isomeri[sz]|rearrang|cycli[sz]|tautomer", re.I)
# Sentences that deny a route, or name the compound as the starting point of one.
NEGATION = re.compile(r"\b(cannot|can ?not|not be|unlike|instead of|rather than|failed|unsuccessful|starting material|"
                      r"precursor|converted (?:in)?to|used (?:as|in|for|to)|gives|yields|degrades?|decomposes?)\b", re.I)


def _side_combos(st: "Structures") -> dict[tuple, list[tuple[int, str]]]:
    """Formula of every choice of at most two side products (1 to 3 of each) -> that choice."""
    out: dict[tuple, list[tuple[int, str]]] = {(): []}
    forms = [(s, st.formula(s)) for s in SIDE_PRODUCTS]
    for i, (a, fa) in enumerate(forms):
        for na in (1, 2, 3):
            c = Counter({k: v * na for k, v in fa.items()})
            out.setdefault(_key(c), [(na, a)])
            for b, fb in forms[i + 1:]:
                for nb in (1, 2, 3):
                    c2 = c + Counter({k: v * nb for k, v in fb.items()})
                    c2.update({k: 0 for k in fb})  # keep zero charges from vanishing unevenly
                    out.setdefault(_key(c2), [(na, a), (nb, b)])
    return out


def _sentences(text: str):
    """Sentences of the preparation sections, with their links kept."""
    heads = list(PREP_SECTION.finditer(text))
    for h in heads:
        level = len(h.group(1))
        nxt = re.compile(r"^={2,%d}[^=].*?={2,%d}\s*$" % (level, level), re.M).search(text, h.end())
        body = text[h.end(): nxt.start() if nxt else len(text)]
        body = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|\{\{(?:cite|citation|cn|citation needed)[^{}]*\}\}", "", body, flags=re.S | re.I)
        body = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", body)
        for para in body.split("\n"):
            if para.startswith((":", "{", "|", "!", "*")) and not para.startswith("* "):
                continue
            yield from (s.strip() for s in re.split(r"(?<=[a-z0-9)\]])\.\s+(?=[A-Z\[])", para) if PREP_VERB.search(s))


def balance(own: str, named: list[str], plain: str, st: "Structures", side: dict) -> list[str]:
    """Reaction SMILES in which the fewest of the named compounds (with small whole-number
    amounts) give the compound plus at most two simple side products, atom for atom."""
    target = st.formula(own)
    if target is None or Chem.MolFromSmiles(own).GetNumHeavyAtoms() > 30:
        return []
    own_c = _canon(own)
    for stem, smi in IMPLIED.items():
        if re.search(stem, plain, re.I):
            named = [*named, smi]
    cands = []
    for smi in named:
        c = _canon(smi)
        if c and c != own_c and st.formula(smi) is not None and c not in cands and len(cands) < 8:
            cands.append(c)
    best: list[tuple] = []
    for size in (1, 2, 3):
        for subset in itertools.combinations(cands, size):
            for coefs in itertools.product((1, 2, 3), repeat=size):
                for pn in (1, 2, 3):
                    diff = Counter()
                    for n, s in zip(coefs, subset):
                        for k, v in st.formula(s).items():
                            diff[k] += n * v
                    for k, v in target.items():
                        diff[k] -= pn * v
                    if any(v < 0 for v in diff.values()):
                        continue
                    extra = side.get(_key(diff))
                    if extra is None or any(s in subset for _, s in extra):
                        continue
                    if size == 1 and not extra and not ISOMERISE.search(plain):
                        continue  # same formula: a solvent or by-product named in passing, not a route
                    best.append((size + len(extra), sum(coefs) + pn, subset, extra))
        if best:
            break
    best.sort(key=lambda b: (b[0], b[1]))
    out = []
    for n_species, n_coef, subset, extra in best:
        if (n_species, n_coef) != best[0][:2]:
            break
        right = sorted({own_c, *(s for _, s in extra)})
        out.append(f"{'.'.join(sorted(subset))}>>{'.'.join(right)}")
    return out


def prose_candidates(title: str, own: str, text: str, st: "Structures", side: dict, lower: dict) -> list[tuple[str, str]]:
    """(reaction SMILES, sentence) for sentences that name a balanced route to the article's compound."""
    out = []
    # The sentence must be about making this compound: its name (or "It") comes before the verb.
    subject = re.compile(r"(?:^|\W)(?:%s|it|this compound|this salt|the compound)(?:\W|$)" % re.escape(title.split(" (")[0]), re.I)
    for sent in _sentences(text):
        if NEGATION.search(sent):
            continue
        plain = LINK.sub(lambda m: m.group(2) or m.group(1), sent)
        verb = PREP_VERB.search(plain)
        if not verb or not subject.search(plain[: verb.start()]):
            continue
        names = {}
        for name, smi in NAMED.items():
            if re.search(r"\b%s\b" % name, plain, re.I):
                names[name] = smi
        for lm in LINK.finditer(sent):
            t = lm.group(1).strip()
            t = t[:1].upper() + t[1:]
            if t.lower() not in NAMED and t in st.by_title:
                names[t] = st.by_title[t]
        for word in re.findall(r"[A-Za-z0-9,()'-]+(?:\s[a-z]+)?", plain):
            for w in (word, word.split(" ")[0]):
                if w.lower() in lower:
                    names.setdefault(w, lower[w.lower()])
        out.extend((rxn, plain[:400]) for rxn in balance(own, list(names.values()), plain, st, side))
    return out


def extract(folder: Path) -> None:
    st = Structures(folder / "compounds.csv")
    side_combos = _side_combos(st)
    # Compound titles by lower case, for names written without a link (ethanol, 2-butene).
    lower = {t.lower(): s for t, s in st.by_title.items() if not re.search(r"\s", t) or t.count(" ") < 2}
    out_rows, report = [], Counter()
    seen = set()
    for line in open(folder / "pages.jsonl", encoding="utf-8"):
        page = json.loads(line)
        text = page["text"]
        own = st.by_title.get(page["title"])
        candidates = {}
        if own:
            candidates[page["title"]] = own
        for lm in LINK.finditer(text):
            t = lm.group(1).strip()
            if t:
                t = t[0].upper() + t[1:]
                if t in st.by_title:
                    candidates[t] = st.by_title[t]
        for eq in [*equations(text), *plain_equations(text)]:
            report["equations"] += 1
            sides = ARROW.split(eq)
            if len(sides) != 2:
                report["not one arrow"] += 1
                continue
            parsed = []
            for side in sides:
                items = [x for x in re.split(r"\s+\+\s+", side) if x.strip()]
                parsed.append([resolve(x, candidates, st) for x in items])
            left, right = parsed
            if not left or not right or any(x is None for x in left + right):
                report["species not resolved"] += 1
                continue
            if not balanced(left, right, st):
                report["not balanced"] += 1
                continue
            l_smi = sorted({s for _, s in left})
            r_smi = sorted({s for _, s in right})
            if set(l_smi) & set(r_smi):
                report["same species both sides"] += 1
                continue
            rxn = f"{'.'.join(l_smi)}>>{'.'.join(r_smi)}"
            if rxn in seen:
                report["duplicate"] += 1
                continue
            seen.add(rxn)
            report["kept"] += 1
            out_rows.append((rxn, page["title"], page["revid"], eq, own or ""))
        if own:
            for rxn, sent in prose_candidates(page["title"], own, text, st, side_combos, lower):
                report["sentences"] += 1
                if rxn in seen:
                    report["duplicate"] += 1
                    continue
                seen.add(rxn)
                report["kept from sentences"] += 1
                out_rows.append((rxn, page["title"], page["revid"], "sentence: " + sent, own))
    with open(folder / "wiki_reactions.tsv", "w", encoding="utf-8") as f:
        for rxn, title, revid, eq, own in out_rows:
            f.write(f"{rxn}\t{title}\t{revid}\t{eq.replace(chr(9), ' ').replace(chr(10), ' ')}\t{own}\n")
    for k, v in report.most_common():
        print(f"  {k}: {v}")
    print(f"{len(out_rows)} reactions -> {folder / 'wiki_reactions.tsv'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "extract"])
    ap.add_argument("dir", type=Path)
    args = ap.parse_args()
    (fetch if args.step == "fetch" else extract)(args.dir)


if __name__ == "__main__":
    sys.exit(main())
