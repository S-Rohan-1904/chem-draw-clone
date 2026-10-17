"""Benchmark the 1H and 13C shift predictors against experimental shifts.

The test molecules are the nmrshiftdb2 records held out of the index
(scripts/nmr_env.py --holdout 10 --test docs/benchmark/nmr_test.jsonl), so the
local predictor never saw them. Each predictor is scored per atom on:

- MAE and RMSE in ppm;
- the share of atoms within 2 and 5 ppm (13C) or 0.2 and 0.5 ppm (1H);
- coverage, the share of atoms it predicts at all.

Predictors: "local" (app.nmr_env with the held-out index), "rules" (the additive
rules in app.spectra), "site" (app.spectra.nmr, what the card shows: shifts per
symmetry class) and, for a sample, "nmrshiftdb2" (the live HOSE-code service,
which has seen these molecules, so its numbers are optimistic).

Results are appended to docs/spectra-benchmark.md under --label.

Usage: uv run python scripts/eval_spectra.py --label "S0 baseline" --index /tmp/nmr_env_train.db [--remote 150]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
DOCS = ROOT.parent / "docs"
TEST = DOCS / "benchmark" / "nmr_test.jsonl"
REPORT = DOCS / "spectra-benchmark.md"
BANDS = {"c": (2.0, 5.0), "h": (0.2, 0.5)}


def load(limit: int) -> list[dict]:
    rows = [json.loads(line) for line in TEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        r["c"] = {int(k): v for k, v in r["c"].items()}
        r["h"] = {int(k): v for k, v in r["h"].items()}
    rows = [r for r in rows if Chem.MolFromSmiles(r["smiles"]) is not None]
    return rows[:limit] if limit else rows


def local(mol: Chem.Mol) -> dict[str, dict[int, float]]:
    from app import nmr_env

    p = nmr_env.predict(mol)
    return {"c": {i: v["shift"] for i, v in enumerate(p["C"]) if v}, "h": {i: v["shift"] for i, v in enumerate(p["H"]) if v}}


def rules(mol: Chem.Mol) -> dict[str, dict[int, float]]:
    from app import spectra

    mh = Chem.AddHs(mol)
    out: dict[str, dict[int, float]] = {"c": {}, "h": {}}
    for a in mh.GetAtoms():
        if a.GetIdx() >= mol.GetNumAtoms():
            continue
        if a.GetAtomicNum() == 6:
            out["c"][a.GetIdx()] = spectra._c_shift(a)[0]
        if any(n.GetAtomicNum() == 1 for n in a.GetNeighbors()):
            out["h"][a.GetIdx()] = spectra._h_shift(a, mh)[0]
    return out


def site(smiles: str) -> dict[str, dict[int, float]]:
    """Shifts as the Spectra card shows them (one per symmetry class), spread back to atoms."""
    from app import spectra

    data, _ = spectra.nmr(smiles)
    out: dict[str, dict[int, float]] = {"c": {}, "h": {}}
    for nuc in ("c", "h"):
        for p in data[nuc]["peaks"]:
            for i in p["atoms"]:
                out[nuc][i] = p["shift"]
    return out


# The live nmrshiftdb2 prediction service, which the card no longer calls; kept here for comparison.
NMRSHIFTDB = "https://nmrshiftdb.nmr.uni-koeln.de/NmrshiftdbServlet/nmrshiftdbaction/predict/smiles/{}/spectrumtype/{}"


def _cml_peaks(text: str) -> list[tuple[float, str]]:
    """[(shift, 'aN')] from a nmrshiftdb2 prediction (CML)."""
    root = ET.fromstring(text)
    out = []
    for peak in root.iter():
        if peak.tag.endswith("peak") and "xValue" in peak.attrib and "atomRefs" in peak.attrib:
            for ref in peak.attrib["atomRefs"].split():
                out.append((float(peak.attrib["xValue"]), ref))
    return out


def map_atom_refs(mol: Chem.Mol) -> dict[str, tuple[int, int]]:
    """'aN' -> (heavy atom index, parent heavy atom index). nmrshiftdb2 numbers
    heavy atoms in SMILES order, then appends hydrogens per heavy atom in order."""
    refs: dict[str, tuple[int, int]] = {}
    n = 1
    for a in mol.GetAtoms():
        refs[f"a{n}"] = (a.GetIdx(), a.GetIdx())
        n += 1
    for a in mol.GetAtoms():
        for _ in range(a.GetTotalNumHs(includeNeighbors=True)):
            refs[f"a{n}"] = (-1, a.GetIdx())
            n += 1
    return refs


def remote(smiles: str, mol: Chem.Mol) -> dict[str, dict[int, float]] | None:
    import httpx
    from urllib.parse import quote

    out: dict[str, dict[int, float]] = {"c": {}, "h": {}}
    refs = map_atom_refs(mol)
    try:
        with httpx.Client(timeout=20) as client:
            for kind, nuc in (("13C", "c"), ("1H", "h")):
                r = client.get(NMRSHIFTDB.format(quote(smiles, safe=""), kind))
                if r.status_code != 200 or not r.text.lstrip().startswith("<cml"):
                    return None
                by_atom: dict[int, list[float]] = {}
                for shift, ref in _cml_peaks(r.text):
                    if ref not in refs:
                        continue
                    heavy, parent = refs[ref]
                    atom = heavy if nuc == "c" else parent
                    if (nuc == "c") == (heavy >= 0):
                        by_atom.setdefault(atom, []).append(shift)
                out[nuc] = {a: sum(v) / len(v) for a, v in by_atom.items()}
    except (httpx.HTTPError, ValueError):
        return None
    return out


def score(pairs: dict[str, list[tuple[float, float | None]]]) -> dict[str, dict]:
    out = {}
    for nuc, items in pairs.items():
        hit = [(e, p) for e, p in items if p is not None]
        errs = [abs(e - p) for e, p in hit]
        lo, hi = BANDS[nuc]
        out[nuc] = {
            "atoms": len(items),
            "coverage": len(hit) / len(items) if items else 0,
            "mae": sum(errs) / len(errs) if errs else float("nan"),
            "rmse": math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else float("nan"),
            "lo": sum(e <= lo for e in errs) / len(errs) if errs else 0,
            "hi": sum(e <= hi for e in errs) / len(errs) if errs else 0,
        }
    return out


def table(results: dict[str, dict[str, dict]], n_mols: dict[str, int]) -> str:
    lines = []
    for nuc, title in (("c", "13C"), ("h", "1H")):
        lo, hi = BANDS[nuc]
        lines.append(f"\n**{title}**\n")
        lines.append(f"| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within {lo:g} | within {hi:g} |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for name, res in results.items():
            r = res[nuc]
            lines.append(f"| {name} | {n_mols[name]} | {r['atoms']} | {100 * r['coverage']:.1f}% | {r['mae']:.2f} | {r['rmse']:.2f} | "
                         f"{100 * r['lo']:.1f}% | {100 * r['hi']:.1f}% |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True)
    ap.add_argument("--index", required=True, help="the held-out index (scripts/nmr_env.py --holdout)")
    ap.add_argument("--limit", type=int, default=0, help="score only the first N test molecules")
    ap.add_argument("--remote", type=int, default=0, help="also ask nmrshiftdb2 for a random sample of N molecules")
    ap.add_argument("--no-site", action="store_true", help="skip the card's own pipeline")
    args = ap.parse_args()

    os.environ["CHEM_NMR_ENV_DB"] = args.index
    os.environ["CHEM_SPECTRA_LOOKUP"] = "0"  # the card's pipeline offline; the service is scored on its own
    rows = load(args.limit)
    t0 = time.time()
    predictors = {"local": lambda r, m: local(m), "rules": lambda r, m: rules(m)}
    if not args.no_site:
        predictors["site"] = lambda r, m: site(r["smiles"])
    pairs = {name: {"c": [], "h": []} for name in predictors}
    for r in rows:
        mol = Chem.MolFromSmiles(r["smiles"])
        for name, f in predictors.items():
            pred = f(r, mol)
            for nuc in ("c", "h"):
                pairs[name][nuc] += [(e, pred[nuc].get(a)) for a, e in r[nuc].items()]
    results = {name: score(p) for name, p in pairs.items()}
    n_mols = {name: len(rows) for name in predictors}
    if args.remote:
        sample = random.Random(3).sample(rows, min(args.remote, len(rows)))
        rp = {"c": [], "h": []}
        answered = 0
        for r in sample:
            mol = Chem.MolFromSmiles(r["smiles"])
            pred = remote(r["smiles"], mol)
            if pred is None:
                continue
            answered += 1
            for nuc in ("c", "h"):
                rp[nuc] += [(e, pred[nuc].get(a)) for a, e in r[nuc].items()]
        # The same sample through the local predictor, for a fair comparison.
        lp = {"c": [], "h": []}
        for r in sample:
            pred = local(Chem.MolFromSmiles(r["smiles"]))
            for nuc in ("c", "h"):
                lp[nuc] += [(e, pred[nuc].get(a)) for a, e in r[nuc].items()]
        results["nmrshiftdb2 service (sample)"] = score(rp)
        results["local (same sample)"] = score(lp)
        n_mols["nmrshiftdb2 service (sample)"] = answered
        n_mols["local (same sample)"] = len(sample)
    text = (f"\n## {args.label} ({date.today().isoformat()})\n\n"
            f"{len(rows)} held-out nmrshiftdb2 molecules, scored in {time.time() - t0:.0f} s.\n" + table(results, n_mols) + "\n")
    if not REPORT.exists():
        REPORT.write_text("# Spectra benchmark\n\nNMR shift predictors against experimental shifts of nmrshiftdb2 molecules held out "
                          "of the local index, produced by `backend/scripts/eval_spectra.py`. Each run is appended below.\n",
                          encoding="utf-8")
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
