# Reviewed textbook routes

`made_by_review.csv` holds drafted "Made by" candidates for the 120 teaching molecules in
`docs/benchmark/molecules.tsv` that had no drawn route in reaction index v5 (no USPTO, CRD,
Rhea, Wikipedia or HSDB reaction makes any stereoisomer of them). Nothing in it is shown on the
site until a reviewer marks it right and it is copied into `backend/app/data/curated_reactions.tsv`.

There are 131 rows: 109 routes for 98 molecules, and 22 molecules flagged as having no common
preparation (branched alkanes like 3-methylhexane, the spiro naming examples, trans isomers that
hydrogenation cannot give, metal counterions). Each row is drafted from standard textbook
chemistry and cites a textbook or the original paper. The drafts were checked by machine only:
every SMILES parses, the product is the target with its stereochemistry (same full InChIKey),
every element of the product comes from the left side, and all 109 routes map with RXNMapper,
index and draw. The chemistry and the citations still need a chemist.

## Columns

| column | meaning |
|---|---|
| `id` | row id, kept in the curated file and shown as the route's reference id |
| `target_name`, `target_smiles` | the molecule, SMILES as in the benchmark |
| `benchmark_name` | set when the benchmark gives this SMILES another molecule's name (see below) |
| `kind` | `route`, or `no_preparation` for a molecule with no real preparation |
| `reaction_smiles` | reactants>reagents>products, with stereochemistry |
| `conditions` | reagents and conditions in words (for the reviewer, not shown) |
| `stereo_note` | why the route gives this stereoisomer, shown under the route on the card |
| `reference` | textbook (with topic) or paper, shown as the route's reference |
| `card_note` | for `no_preparation` rows, the note the card shows instead of "no recorded reactions" |
| `confidence` | the drafter's confidence: high, medium or low |
| `drafter_comment` | what to check (a citation page, a racemic route for a single enantiomer, mixtures) |
| `verdict` | **fill in**: `right` or `wrong` |
| `reviewer` | **fill in**: who reviewed the row |
| `reviewer_comment` | optional |

Text in `stereo_note`, `reference` and `card_note` appears on the site, so edits there should keep
to the site rule: colons and hyphens are fine, no semicolons and no long dashes. To correct a row
rather than reject it, edit the row and mark it right.

## Accepting rows

```bash
cd backend
uv run python scripts/curated_reactions.py check ../docs/curated/made_by_review.csv
uv run python scripts/curated_reactions.py accept ../docs/curated/made_by_review.csv
```

`accept` copies rows marked `right` that name a reviewer and pass the checks, and skips rows
already in the curated file. `no_preparation` notes show at once. Routes need the mapping step and
an index rebuild (README, Reaction index).

## Notes found while drafting

- Several teaching entries list several molecules at once ("1-chloropropane 2-chloropropane
  2-bromopropane 2-bromo-2-methylpropane"). `_single` in `backend/scripts/eval_reactions.py` pairs the
  names with the SMILES in written order, but the resolved SMILES are sorted, so the benchmark gives
  some molecules the wrong name (CC(C)(C)Br is called 1-chloropropane, C1CCCCCC1 cyclohexene). The
  sheet uses the right names and keeps the benchmark's in `benchmark_name`.
- If every draft were accepted, teaching Made by would go from 80.7% to about 96.5% (599 of 621), and
  every remaining molecule would carry a no common preparation note.
