# Literature benchmark

Coverage and top-5 quality of the Literature card, produced by `backend/scripts/eval_literature.py` over 60 teaching molecules, 20 drugs, 12 building blocks, 8 natural products and 2 unknown structures. Each run is appended below.

## L0 baseline: main before this change (2026-10-16)

Scored with this script against the code on main at b4e39f4 (three sources: ChemRxiv by name, PubMed links
from PubChem, reaction-index patents). 102 molecules, median 4.3 s each with an empty cache (slowest 8.4 s).
OpenAlex facts for 345 of 345 top-5 journal DOIs.

**teaching** (60 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 71.7% | 51.7% | 49.5% | 34.4% | 38.8% | – | 2 |
| chemrxiv | 81.7% | 51.7% | 31.3% | – | – | – | 0 |
| patents | 88.3% | 76.7% | 0.8% | – | – | 0.0% | 0 |

**drugs** (20 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 96.0% | 1.0% | 49.5% | – | 0 |
| chemrxiv | 100.0% | 45.0% | 13.7% | – | – | – | 0 |
| patents | 100.0% | 30.0% | 16.2% | – | – | 0.0% | 0 |

**building blocks** (12 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 75.0% | 66.7% | 17.1% | 55.0% | 32.5% | – | 0 |
| chemrxiv | 100.0% | 75.0% | 1.9% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 0.0% | – | – | 0.0% | 0 |

**natural products** (8 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 75.0% | 75.0% | 100.0% | 0.0% | 60.0% | – | 2 |
| chemrxiv | 100.0% | 75.0% | 45.7% | – | – | – | 0 |
| patents | 100.0% | 50.0% | 14.3% | – | – | 0.0% | 0 |

**unknown** (2 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 0.0% | 0.0% | n/a | n/a | n/a | – | 0 |
| chemrxiv | 0.0% | 0.0% | n/a | – | – | – | 0 |
| patents | 0.0% | 0.0% | n/a | – | – | n/a | 0 |

**all** (102 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 76.5% | 63.7% | 63.1% | 24.4% | 42.9% | – | 4 |
| chemrxiv | 87.3% | 53.9% | 24.8% | – | – | – | 0 |
| patents | 91.2% | 66.7% | 4.2% | – | – | 0.0% | 0 |

## L1 five journal sources, SureChEMBL, ranking (2026-10-16)

102 molecules, median 13.4 s each with an empty cache (slowest 32.2 s). OpenAlex facts for 463 of 464 top-5 journal DOIs.

**teaching** (60 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 95.0% | 91.7% | 67.5% | 59.4% | 30.2% | – | 0 |
| chemrxiv | 83.3% | 60.0% | 31.8% | – | – | – | 0 |
| patents | 100.0% | 98.3% | 7.4% | – | – | 11.0% | 0 |

**drugs** (20 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 100.0% | 37.0% | 38.0% | – | 0 |
| chemrxiv | 100.0% | 45.0% | 13.7% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 38.0% | – | – | 0.0% | 0 |

**building blocks** (12 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 60.0% | 86.7% | 38.3% | – | 0 |
| chemrxiv | 100.0% | 66.7% | 2.1% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 10.0% | – | – | 0.4% | 0 |

**natural products** (8 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 97.5% | 47.5% | 45.0% | – | 0 |
| chemrxiv | 87.5% | 62.5% | 53.3% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 70.0% | – | – | 2.0% | 0 |

**unknown** (2 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 0.0% | 0.0% | n/a | n/a | n/a | – | 0 |
| chemrxiv | 0.0% | 0.0% | n/a | – | – | – | 0 |
| patents | 0.0% | 0.0% | n/a | – | – | n/a | 0 |

**all** (102 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 95.1% | 93.1% | 75.8% | 57.1% | 34.1% | – | 0 |
| chemrxiv | 87.3% | 56.9% | 26.0% | – | – | – | 0 |
| patents | 98.0% | 97.1% | 18.9% | – | – | 6.8% | 0 |

## L2 newest SureChEMBL pages, free full text ranked up (2026-10-16)

102 molecules, median 11.8 s each with an empty cache (slowest 29.2 s). OpenAlex facts for 463 of 464 top-5 journal DOIs.

**teaching** (60 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 95.0% | 91.7% | 67.1% | 61.2% | 36.7% | – | 0 |
| chemrxiv | 83.3% | 60.0% | 31.8% | – | – | – | 0 |
| patents | 100.0% | 98.3% | 7.4% | – | – | 64.6% | 0 |

**drugs** (20 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 100.0% | 41.0% | 50.0% | – | 0 |
| chemrxiv | 100.0% | 45.0% | 13.7% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 40.0% | – | – | 77.9% | 0 |

**building blocks** (12 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 60.0% | 86.7% | 50.0% | – | 0 |
| chemrxiv | 100.0% | 66.7% | 2.1% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 13.3% | – | – | 68.7% | 0 |

**natural products** (8 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 100.0% | 42.5% | 52.5% | – | 0 |
| chemrxiv | 87.5% | 62.5% | 53.3% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 72.5% | – | – | 72.0% | 0 |

**unknown** (2 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 0.0% | 0.0% | n/a | n/a | n/a | – | 0 |
| chemrxiv | 0.0% | 0.0% | n/a | – | – | – | 0 |
| patents | 0.0% | 0.0% | n/a | – | – | n/a | 0 |

**all** (102 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 95.1% | 93.1% | 75.8% | 58.6% | 42.5% | – | 0 |
| chemrxiv | 87.3% | 56.9% | 26.0% | – | – | – | 0 |
| patents | 98.0% | 97.1% | 19.9% | – | – | 68.2% | 0 |

## L3 ChEMBL through UniChem, card waits at most 10 s (2026-10-16)

**OpenAlex's daily budget for the API key ran out during this run** (10,000 credits a day, after four
earlier runs the same day), so OpenAlex answered only part of the time: the ChemRxiv list, the OpenAlex
journal source, the chemistry share and the free-full-text share are lower than the code delivers and are
not comparable with L2. PubMed, ChEMBL, Europe PMC, the ORD and SureChEMBL were unaffected. Timing is with
`budget=None` (the benchmark waits for every source; the site answers within 10 s and fills in the rest).
102 molecules, median 12.9 s each with an empty cache (slowest 37.9 s). OpenAlex facts for 300 of 450 top-5 journal DOIs.

**teaching** (60 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 93.3% | 88.3% | 59.8% | 49.5% | 30.2% | – | 0 |
| chemrxiv | 76.7% | 51.7% | 41.5% | – | – | – | 0 |
| patents | 100.0% | 98.3% | 7.1% | – | – | 64.6% | 0 |

**drugs** (20 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 100.0% | 21.8% | 43.6% | – | 0 |
| chemrxiv | 45.0% | 5.0% | 100.0% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 40.0% | – | – | 77.9% | 0 |

**building blocks** (12 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 18.3% | 61.0% | 39.0% | – | 0 |
| chemrxiv | 8.3% | 0.0% | 50.0% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 13.3% | – | – | 68.7% | 0 |

**natural products** (8 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 100.0% | 100.0% | 92.5% | 12.9% | 54.8% | – | 0 |
| chemrxiv | 87.5% | 37.5% | 95.7% | – | – | – | 0 |
| patents | 100.0% | 100.0% | 70.0% | – | – | 72.0% | 0 |

**unknown** (2 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 0.0% | 0.0% | n/a | n/a | n/a | – | 0 |
| chemrxiv | 0.0% | 0.0% | n/a | – | – | – | 0 |
| patents | 0.0% | 0.0% | n/a | – | – | n/a | 0 |

**all** (102 molecules)

| list | at least 1 | at least 5 | top 5 name it | top 5 chemistry | top 5 free full text | from 2017 on | not reachable |
|---|---|---|---|---|---|---|---|
| journals | 94.1% | 91.2% | 65.8% | 42.4% | 36.2% | – | 0 |
| chemrxiv | 61.8% | 34.3% | 51.3% | – | – | – | 0 |
| patents | 98.0% | 97.1% | 19.5% | – | – | 68.2% | 0 |
