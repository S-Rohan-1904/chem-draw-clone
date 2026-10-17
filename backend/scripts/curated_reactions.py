"""Check a review sheet of candidate textbook routes, and copy the accepted rows into the curated file.

The review sheet (docs/curated/made_by_review.csv) holds drafted candidates, one per row:
a route (reaction SMILES with stereochemistry, conditions, reference) or a "no common
preparation" note. A reviewer fills in verdict (right or wrong), reviewer and, if they like,
reviewer_comment. Only rows marked right with a reviewer named are copied into
app/data/curated_reactions.tsv, which the index builder and the lookup read (app/curated.py).

  uv run python scripts/curated_reactions.py check ../docs/curated/made_by_review.csv
  uv run python scripts/curated_reactions.py accept ../docs/curated/made_by_review.csv

After accepting routes, map them and rebuild the index (README, Reaction index):
  $MAP curated app/data/curated_reactions.tsv curated_mapped.tsv
  uv run python scripts/build_reactions.py ... --curated curated_mapped.tsv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import curated  # noqa: E402

ACCEPT = {"right", "yes", "y", "correct", "ok"}
REJECT = {"wrong", "no", "n", "incorrect"}


def read_review(file: Path) -> list[dict]:
    with open(file, encoding="utf-8-sig", newline="") as f:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def to_curated(row: dict) -> dict:
    """A review sheet row as a curated file row."""
    kind = row["kind"]
    return {
        "id": row["id"],
        "kind": kind,
        "name": row["target_name"],
        "product_smiles": row["target_smiles"],
        "reaction_smiles": row["reaction_smiles"] if kind == "route" else "",
        "reference": row["reference"],
        "note": row["card_note"] if kind == "no_preparation" else row["stereo_note"],
        "reviewed_by": row.get("reviewer", ""),
        "reviewed_on": row.get("reviewed_on", "") or date.today().isoformat(),
    }


def check(rows: list[dict]) -> int:
    """Print every problem; drafted rows are checked as if a reviewer had signed them."""
    bad = 0
    for row in rows:
        c = to_curated(row)
        c["reviewed_by"] = c["reviewed_by"] or "draft"
        found = curated.problems(c)
        verdict = row.get("verdict", "").lower()
        if verdict and verdict not in ACCEPT | REJECT:
            found.append(f"verdict {row['verdict']!r} is neither right nor wrong")
        if found:
            bad += 1
            print(f"{row['id']} {row['target_name']}: {'; '.join(found)}")
    return bad


def accept(rows: list[dict], out: Path) -> tuple[int, int, list[str]]:
    """Add the rows marked right to the curated file. Returns (added, already there, problems)."""
    have = curated.read(out)
    ids = {r["id"] for r in have}
    added, kept, issues = 0, 0, []
    for row in rows:
        if row.get("verdict", "").lower() not in ACCEPT:
            continue
        c = to_curated(row)
        if c["id"] in ids:
            kept += 1
            continue
        found = curated.problems(c)
        if found:
            issues.append(f"{c['id']} {c['name']}: {'; '.join(found)}")
            continue
        have.append(c)
        ids.add(c["id"])
        added += 1
    if added:
        curated.write(out, have)
    return added, kept, issues


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check every row of a review sheet")
    c.add_argument("review", type=Path)
    a = sub.add_parser("accept", help="copy the rows marked right into the curated file")
    a.add_argument("review", type=Path)
    a.add_argument("--out", type=Path, default=curated.DEFAULT_PATH)
    args = ap.parse_args()
    rows = read_review(args.review)
    if args.cmd == "check":
        bad = check(rows)
        print(f"{len(rows)} rows, {bad} with problems")
        sys.exit(1 if bad else 0)
    added, kept, issues = accept(rows, args.out)
    for line in issues:
        print(line)
    print(f"{added} rows added to {args.out}, {kept} already there, {len(issues)} refused")
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
