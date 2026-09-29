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

## M1 applications and Rhea, M3 literature, making text (2026-09-29)

Index 1273131 reactions, 1534228 molecules, built 2026-09-28. Reactions scored in 1 s. Precision sheet `docs/benchmark/precision_m1_applications_and_rhea__m3_literature__making_text.csv`.

**teaching** (670 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 76.7% | 51.2% |
| Used in, with enzyme reactions | 77.2% | 56.0% |
| Made by | 46.6% | 21.6% |
| Made by, with enzyme reactions | 58.2% | 29.4% |
| Made by, with PubChem methods and Wikipedia | 73.7% | |

| literature source | at least 1 item |
|---|---|
| chemrxiv | 56.4% |
| journals | 6.7% |
| patents | 78.2% |
| pubchem methods | 51.6% |
| wikipedia | 54.8% |

**drugs** (50 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 84.0% | 20.0% |
| Used in, with enzyme reactions | 84.0% | 20.0% |
| Made by | 92.0% | 34.0% |
| Made by, with enzyme reactions | 94.0% | 34.0% |
| Made by, with PubChem methods and Wikipedia | 96.0% | |

| literature source | at least 1 item |
|---|---|
| chemrxiv | 48.0% |
| journals | 0.0% |
| patents | 98.0% |
| pubchem methods | 66.0% |
| wikipedia | 26.0% |

**all** (720 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 77.2% | 49.0% |
| Used in, with enzyme reactions | 77.6% | 53.5% |
| Made by | 49.7% | 22.5% |
| Made by, with enzyme reactions | 60.7% | 29.7% |
| Made by, with PubChem methods and Wikipedia | 75.3% | |

| literature source | at least 1 item |
|---|---|
| chemrxiv | 55.8% |
| journals | 6.2% |
| patents | 79.6% |
| pubchem methods | 52.6% |
| wikipedia | 52.8% |

## M1 USPTO grants and applications, Rhea (single molecules) (2026-09-29)

Index 1273131 reactions, 1534228 molecules, built 2026-09-28. Reactions scored in 1 s. Precision sheet `docs/benchmark/precision_m1_uspto_grants_and_applications__rhea__single_molecules.csv`.

**teaching** (621 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 88.6% | 60.1% |
| Used in, with enzyme reactions | 89.0% | 64.6% |
| Made by | 48.6% | 20.6% |
| Made by, with enzyme reactions | 62.5% | 27.9% |

**drugs** (50 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 84.0% | 20.0% |
| Used in, with enzyme reactions | 84.0% | 20.0% |
| Made by | 92.0% | 34.0% |
| Made by, with enzyme reactions | 94.0% | 34.0% |

**all** (671 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 88.2% | 57.1% |
| Used in, with enzyme reactions | 88.7% | 61.3% |
| Made by | 51.9% | 21.6% |
| Made by, with enzyme reactions | 64.8% | 28.3% |

## M1 plus CRD (2026-09-29)

Index 1948724 reactions, 2109129 molecules, built 2026-09-29. Reactions scored in 1 s. Precision sheet `docs/benchmark/precision_m1_plus_crd.csv`.

**teaching** (621 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 89.7% | 64.6% |
| Used in, with enzyme reactions | 90.2% | 67.8% |
| Made by | 55.4% | 22.4% |
| Made by, with enzyme reactions | 66.0% | 30.3% |

**drugs** (50 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 90.0% | 22.0% |
| Used in, with enzyme reactions | 90.0% | 22.0% |
| Made by | 96.0% | 42.0% |
| Made by, with enzyme reactions | 98.0% | 42.0% |

**all** (671 molecules)

| | at least 1 type | at least 5 types |
|---|---|---|
| Used in | 89.7% | 61.4% |
| Used in, with enzyme reactions | 90.2% | 64.4% |
| Made by | 58.4% | 23.8% |
| Made by, with enzyme reactions | 68.4% | 31.1% |
