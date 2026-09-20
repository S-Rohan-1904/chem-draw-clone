"""Help for mistyped names: plain-English reasons, the bad fragment's span,
and "did you mean" candidates. Candidates are only ever suggested, never
applied automatically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process
from rapidfuzz.distance import DamerauLevenshtein

from . import opsin

DATA = Path(__file__).resolve().parent / "data" / "common_names.txt"

# Word pieces OPSIN understands. Used to spot the misspelt piece of a name.
MORPHEMES = sorted(set("""
meth eth prop but pent hex hept oct non dec undec dodec tridec tetradec pentadec hexadec heptadec octadec nonadec icos eicos
di tri tetra penta hexa hepta octa nona deca bis tris tetrakis
ane ene yne diene triene diyne enyne an en yn
ol diol triol al dial one dione oic acid dioic amine diamine amide imine nitrile oate ate ide ium
yl ylidene ylidyne oxy oxo hydroxy amino nitro cyano azido thio sulfanyl sulfonyl sulfinyl carboxy carbamoyl formyl acetyl benzoyl
fluoro chloro bromo iodo fluoride chloride bromide iodide
methoxy ethoxy propoxy butoxy phenoxy benzyloxy acetoxy
phenyl benzyl naphthyl tolyl phenylene benzene toluene phenol aniline anisole naphthalene anthracene phenanthrene biphenyl styrene
cyclo bicyclo tricyclo spiro benzo naphtho
pyridine pyridin pyrrole pyrrol furan thiophene thiophen imidazole imidazol pyrimidine pyrimidin purine purin indole indol quinoline quinolin piperidine piperidin pyrrolidine pyrrolidin morpholine morpholin piperazine piperazin oxirane oxiran oxolane oxolan oxane oxan azetidine aziridine thiazole oxazole pyrazole pyrazine pyridazine triazole tetrazole
iso sec tert neo cis trans endo exo syn anti alpha beta gamma delta
sulf sulfo sulfide sulfoxide sulfone sulfonic sulfate thiol thione phosph phosphate phosphonic phosphane silane boron borane
carbon carbonyl carboxylic carbaldehyde carbonitrile carboxamide carboxylate
hydro dehydro dihydro tetrahydro hexahydro octahydro decahydro perhydro
glyc glucose fructose galactose mannose ribose xylose arabinose sucrose lactose maltose
alanine glycine valine leucine isoleucine proline phenylalanine tyrosine tryptophan serine threonine cysteine methionine asparagine glutamine aspartic glutamic lysine arginine histidine
acetic formic oxalic citric lactic tartaric malic fumaric maleic succinic adipic stearic palmitic oleic linoleic benzoic salicylic
acetone acetaldehyde formaldehyde acetonitrile acetamide anhydride acetyl chloride ether ester
ethylene propylene isoprene isobutane isopentane neopentane isopropanol butanol propanol ethanol methanol glycerol glycol
urea thiourea guanidine hydrazine hydroxylamine cholesterol caffeine nicotine adenine guanine cytosine thymine uracil
""".split()), key=len, reverse=True)
_MORPHEME_SET = set(MORPHEMES)


@dataclass
class Diagnosis:
    reason: str
    highlight: tuple[int, int] | None = None
    suggestions: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def known_names() -> list[str]:
    names = [line.strip() for line in DATA.read_text().splitlines() if line.strip()]
    return names


def _segmentable(word: str) -> bool:
    """Can the lowercase alphabetic word be tiled with known morphemes?"""
    n = len(word)
    ok = [False] * (n + 1)
    ok[0] = True
    for i in range(n):
        if not ok[i]:
            continue
        for m in MORPHEMES:
            if word.startswith(m, i):
                ok[i + len(m)] = True
    return ok[n]


def _unsegmentable_words(name: str) -> list[tuple[int, int, str]]:
    out = []
    for m in re.finditer(r"[A-Za-z]+", name):
        w = m.group(0).lower()
        if len(w) >= 3 and not _segmentable(w):
            out.append((m.start(), m.end(), m.group(0)))
    return out


def _tile_with_one_fix(word: str) -> list[str]:
    """Rewrites of `word` where one unknown stretch is replaced by a morpheme
    within edit distance 1 (2 for stretches of 5+ letters). Returns candidates
    that tile completely after the fix."""
    n = len(word)
    # ok[i] = word[:i] tiles cleanly; ok_rev[i] = word[i:] tiles cleanly
    ok = [False] * (n + 1)
    ok[0] = True
    for i in range(n):
        if ok[i]:
            for m in MORPHEMES:
                if word.startswith(m, i):
                    ok[i + len(m)] = True
    ok_rev = [False] * (n + 1)
    ok_rev[n] = True
    for i in range(n, -1, -1):
        for m in MORPHEMES:
            if i + len(m) <= n and word.startswith(m, i) and ok_rev[i + len(m)]:
                ok_rev[i] = True
    out: dict[str, int] = {}
    for i in range(n):
        if not ok[i]:
            continue
        for j in range(i + 2, min(n, i + 14) + 1):
            if not ok_rev[j]:
                continue
            piece = word[i:j]
            if piece in _MORPHEME_SET:
                continue
            limit = 2 if len(piece) >= 5 else 1
            for m in MORPHEMES:
                if abs(len(m) - len(piece)) > limit:
                    continue
                d = DamerauLevenshtein.distance(piece, m, score_cutoff=limit)
                if d <= limit:
                    cand = word[:i] + m + word[j:]
                    if cand != word:
                        out[cand] = min(d, out.get(cand, 99))
    return [c for c, _ in sorted(out.items(), key=lambda kv: (kv[1], len(kv[0])))]


def _parses(name: str) -> bool:
    return bool(opsin.strict.convert(name)[0])


def _spell_candidates(name: str, limit: int = 3) -> list[str]:
    bad = _unsegmentable_words(name)
    if not bad or len(bad) > 2:
        return []
    start, end, word = bad[0]
    results: list[str] = []
    for fixed in _tile_with_one_fix(word.lower())[:40]:
        # keep original capitalisation style for the first letter
        cand = name[:start] + fixed + name[end:]
        if len(bad) == 2:
            s2, e2, w2 = bad[1]
            for fixed2 in _tile_with_one_fix(w2.lower())[:10]:
                cand2 = cand[:s2] + fixed2 + cand[e2:]
                if _parses(cand2):
                    results.append(cand2)
                    if len(results) >= limit:
                        return results
            continue
        if _parses(cand):
            results.append(cand)
            if len(results) >= limit:
                break
    return results


def _fuzzy_known(name: str, extra: list[str], limit: int = 3) -> list[str]:
    pool = list(dict.fromkeys(known_names() + extra))
    hits = process.extract(name, pool, scorer=fuzz.ratio, limit=limit * 2, score_cutoff=80, processor=str.lower)
    out = []
    for cand, _score, _ in hits:
        if cand.lower() != name.lower():
            out.append(cand)
    return out[:limit]


def _rank(name: str, cands: list[str], max_distance: int = 4) -> list[str]:
    scored = [(DamerauLevenshtein.distance(name.lower(), c.lower()), c) for c in dict.fromkeys(cands)]
    return [c for d, c in sorted(scored) if d <= max_distance]


def _plain_reason(opsin_error: str, name: str) -> tuple[str, tuple[int, int] | None]:
    m = re.search(r"The following was not parseable: (.*)$", opsin_error)
    if not m:
        m = re.search(r"uninterpretable: (.*?)(?: The following|$)", opsin_error)
    if m:
        frag = m.group(1).strip()
        pos = name.lower().rfind(frag.lower())
        span = (pos, pos + len(frag)) if pos >= 0 and frag else None
        if span and len(frag) < 3:  # widen a 1-2 letter fragment to its word
            wm = [w for w in re.finditer(r"[A-Za-z]+", name) if w.start() <= span[0] < w.end()]
            if wm:
                span = (wm[0].start(), wm[0].end())
                frag = wm[0].group(0)
        return f'Could not understand "{frag}".', span
    if "Could not find atom" in opsin_error and "stereoChemistry" in opsin_error:
        loc = re.search(r'locant="([^"]*)"', opsin_error)
        return (f"Position {loc.group(1)} is not a stereocentre, so its descriptor cannot be applied." if loc
                else "A stereo descriptor points at an atom that is not a stereocentre."), None
    m = re.search(r"locant(?:s)? ([0-9a-z',]+) (?:is|are|was|were) not (?:found|present|valid)", opsin_error, re.I)
    if m:
        return f"Locant {m.group(1)} does not exist on that chain or ring.", None
    if "Substitutive bond formation" in opsin_error or "bond formation" in opsin_error:
        return "The pieces of this name cannot be joined the way it is written (check locants and substituent names).", None
    if "valency" in opsin_error.lower():
        return "This name asks for more bonds than an atom can have (check locants and multiplicity).", None
    if opsin_error:
        return re.sub(r"<[^>]+>", "", opsin_error).strip(), None
    return "This is not a name OPSIN can interpret.", None


def diagnose(name: str, opsin_error: str, extra_names: list[str] | None = None) -> Diagnosis:
    reason, span = _plain_reason(opsin_error, name)
    suggestions = _rank(name, _spell_candidates(name) + _fuzzy_known(name, extra_names or []))
    return Diagnosis(reason, span, suggestions[:3])


def autocomplete(q: str, extra_names: list[str], limit: int = 8) -> list[str]:
    q = q.strip().lower()
    if len(q) < 2:
        return []
    pool = list(dict.fromkeys(extra_names + known_names()))
    prefix = [n for n in pool if n.lower().startswith(q)]
    inner = [n for n in pool if q in n.lower() and not n.lower().startswith(q)]
    return (prefix + inner)[:limit]
