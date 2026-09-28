# Reaction and literature benchmark

Coverage of the Reactions and Literature cards over the teaching set (app/data/common_names.txt) and 50 drugs, produced by `backend/scripts/eval_reactions.py`. Each run is appended below.

## M0 baseline (2026-09-28)

Index 945347 reactions, 1169824 molecules, built 2026-09-28. Reactions scored in 11 s. Precision sheet `docs/benchmark/precision_m0_baseline.csv`.

**teaching** (670 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 75.5% | 48.7% |
| Made by | 44.6% | 18.2% |

| literature source | at least 1 item |
|---|---|
| chemrxiv | 48.1% |

**drugs** (50 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 74.0% | 20.0% |
| Made by | 92.0% | 22.0% |

| literature source | at least 1 item |
|---|---|
| chemrxiv | 46.0% |

**all** (720 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 75.4% | 46.7% |
| Made by | 47.9% | 18.5% |

| literature source | at least 1 item |
|---|---|
| chemrxiv | 47.9% |
